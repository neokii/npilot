import math
import numpy as np

from common.numpy_fast import clip, interp
from common.realtime import DT_CTRL
from cereal import log
from selfdrive.controls.lib.latcontrol import LatControl, MIN_STEER_SPEED
from selfdrive.controls.lib.pid import PIDController

ERROR_RATE_FRAME = 5

TORQUE_SCALE_BP = [0., 30., 80., 100., 130.]
TORQUE_SCALE_V = [0.2, 0.35, 0.63, 0.67, 0.7]

class LatControlHybrid(LatControl):
  def __init__(self, CP, CI):
    super().__init__(CP, CI)
    self.scale = 1600.
    self.ki = 0.01
    self.dc_gain = 0.0027

    self.A = np.array([0., 1., -0.22619643, 1.21822268]).reshape((2, 2))
    self.B = np.array([-1.92006585e-04, 3.95603032e-05]).reshape((2, 1))
    self.C = np.array([1., 0.]).reshape((1, 2))
    self.K = np.array([-110., 451.]).reshape((1, 2))
    self.L = np.array([0.33, 0.318]).reshape((2, 1))

    self.x_hat = np.array([[0], [0]])
    self.i_unwind_rate = 0.3 * DT_CTRL
    self.i_rate = 1.0 * DT_CTRL

    self.pid = PIDController(k_p=0.2,
                             k_i=0.02,
                             k_f=0.00005,
                             k_d=0.1,
                             pos_limit=1.0, neg_limit=-1.0)
    self.get_steer_feedforward = CI.get_steer_feedforward_function()
    self.errors = []
    self.reset()


  def reset(self):
    super().reset()
    self.i_lqr = 0.0
    self.pid.reset()
    self.errors = []

  def update(self, active, CS, CP, VM, params, last_actuators, desired_curvature, desired_curvature_rate, llk):

    lat_log = log.ControlsState.LateralHybridState.new_message()
    lat_log.steeringAngleDeg = float(CS.steeringAngleDeg)

    angle_steers_des_no_offset = math.degrees(VM.get_steer_from_curvature(-desired_curvature, CS.vEgo, params.roll))

    #torque_scale = (0.45 + CS.vEgo / 60.0)**2  # Scale actuator model with speed
    torque_scale = interp(CS.vEgo * 3.6, TORQUE_SCALE_BP, TORQUE_SCALE_V)

    steering_angle_no_offset = CS.steeringAngleDeg - params.angleOffsetAverageDeg
    desired_angle = angle_steers_des_no_offset
    instant_offset = params.angleOffsetDeg - params.angleOffsetAverageDeg
    desired_angle += instant_offset  # Only add offset that originates from vehicle model errors

    lat_log.steeringAngleDesiredDeg = desired_angle

    # Update Kalman filter
    angle_steers_k = float(self.C.dot(self.x_hat))
    e = steering_angle_no_offset - angle_steers_k
    self.x_hat = self.A.dot(self.x_hat) + self.B.dot(CS.steeringTorqueEps / torque_scale) + self.L.dot(e)

    if CS.vEgo < MIN_STEER_SPEED or not active:
      output_steer = 0.
      lat_log.active = False
      self.reset()
    else:
      lat_log.active = True

      # LQR
      u_lqr = float(desired_angle / self.dc_gain - self.K.dot(self.x_hat))
      lqr_output = torque_scale * u_lqr / self.scale

      # Integrator
      if CS.steeringPressed:
        self.i_lqr -= self.i_unwind_rate * float(np.sign(self.i_lqr))
      else:
        error = desired_angle - angle_steers_k
        i = self.i_lqr + self.ki * self.i_rate * error
        control = lqr_output + i

        if (error >= 0 and (control <= self.steer_max or i < 0.0)) or \
           (error <= 0 and (control >= -self.steer_max or i > 0.0)):
          self.i_lqr = i

      output_steer_lqr = lqr_output + self.i_lqr
      output_steer_lqr = clip(output_steer_lqr, -self.steer_max, self.steer_max)

      # PID
      angle_steers_des = angle_steers_des_no_offset + params.angleOffsetDeg
      error = angle_steers_des - CS.steeringAngleDeg

      self.pid.pos_limit = self.steer_max
      self.pid.neg_limit = -self.steer_max

      steer_feedforward = self.get_steer_feedforward(angle_steers_des_no_offset, CS.vEgo)

      error_rate = 0
      if len(self.errors) >= ERROR_RATE_FRAME:
        error_rate = (error - self.errors[-ERROR_RATE_FRAME]) / ERROR_RATE_FRAME

      self.errors.append(float(error))
      while len(self.errors) > ERROR_RATE_FRAME:
        self.errors.pop(0)

      output_steer_pid = self.pid.update(error,
                                         error_rate=error_rate,
                                         override=CS.steeringPressed,
                                         feedforward=steer_feedforward, speed=CS.vEgo)

      lqr_weight = interp(abs((angle_steers_des + CS.steeringAngleDeg) / 2.), [10., 25.], [1., 0.])
      output_steer = output_steer_lqr * lqr_weight + output_steer_pid * (1. - lqr_weight)

    lat_log.output = output_steer
    lat_log.saturated = self._check_saturation(self.steer_max - abs(output_steer) < 1e-3, CS)
    return output_steer, desired_angle, lat_log
