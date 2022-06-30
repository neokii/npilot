#!/usr/bin/env python3
from typing import List

from cereal import car
from common.numpy_fast import interp
from common.conversions import Conversions as CV
from selfdrive.car.hyundai.values import CAR, Buttons, CarControllerParams
from selfdrive.car import STD_CARGO_KG, scale_rot_inertia, scale_tire_stiffness, gen_empty_fingerprint, get_safety_config
from selfdrive.car.interfaces import CarInterfaceBase
from common.params import Params
from selfdrive.controls.lib.desire_helper import LANE_CHANGE_SPEED_MIN

GearShifter = car.CarState.GearShifter
EventName = car.CarEvent.EventName
ButtonType = car.CarState.ButtonEvent.Type

class CarInterface(CarInterfaceBase):
  def __init__(self, CP, CarController, CarState):
    super().__init__(CP, CarController, CarState)
    self.cp2 = self.CS.get_can2_parser(CP)
    self.mad_mode_enabled = Params().get_bool('MadModeEnabled')

  @staticmethod
  def get_pid_accel_limits(CP, current_speed, cruise_speed):

    v_current_kph = current_speed * CV.MS_TO_KPH

    gas_max_bp = [10., 20., 50., 70., 130., 150.]
    gas_max_v = [1.5, 1.23, 0.67, 0.47, 0.16, 0.1]

    return CarControllerParams.ACCEL_MIN, interp(v_current_kph, gas_max_bp, gas_max_v)

  @staticmethod
  def get_params(candidate, fingerprint=gen_empty_fingerprint(), car_fw=[], disable_radar=False):  # pylint: disable=dangerous-default-value
    ret = CarInterfaceBase.get_std_params(candidate, fingerprint)

    ret.openpilotLongitudinalControl = Params().get_bool('LongControlEnabled')

    ret.carName = "hyundai"
    ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.hyundaiLegacy, 0)]

    tire_stiffness_factor = 1.
    ret.maxSteeringAngleDeg = 1000.

    ret.steerFaultMaxAngle = 85
    ret.steerFaultMaxFrames = 90

    ret.disableLateralLiveTuning = False

    # lateral
    lateral_control = Params().get("LateralControl", encoding='utf-8')
    if lateral_control == 'INDI':
      ret.lateralTuning.init('indi')
      ret.lateralTuning.indi.innerLoopGainBP = [0.]
      ret.lateralTuning.indi.innerLoopGainV = [3.3]
      ret.lateralTuning.indi.outerLoopGainBP = [0.]
      ret.lateralTuning.indi.outerLoopGainV = [2.8]
      ret.lateralTuning.indi.timeConstantBP = [0.]
      ret.lateralTuning.indi.timeConstantV = [1.4]
      ret.lateralTuning.indi.actuatorEffectivenessBP = [0.]
      ret.lateralTuning.indi.actuatorEffectivenessV = [1.8]
    elif lateral_control == 'LQR':
      ret.lateralTuning.init('lqr')

      ret.lateralTuning.lqr.scale = 1600.
      ret.lateralTuning.lqr.ki = 0.01
      ret.lateralTuning.lqr.dcGain = 0.0025

      ret.lateralTuning.lqr.a = [0., 1., -0.22619643, 1.21822268]
      ret.lateralTuning.lqr.b = [-1.92006585e-04, 3.95603032e-05]
      ret.lateralTuning.lqr.c = [1., 0.]
      ret.lateralTuning.lqr.k = [-110., 451.]
      ret.lateralTuning.lqr.l = [0.33, 0.318]
    else:
      ret.lateralTuning.init('torque')
      ret.lateralTuning.torque.useSteeringAngle = True
      max_lat_accel = 2.5
      ret.lateralTuning.torque.kp = 1.0 / max_lat_accel
      ret.lateralTuning.torque.kf = 1.0 / max_lat_accel
      ret.lateralTuning.torque.ki = 0.1 / max_lat_accel
      ret.lateralTuning.torque.friction = 0.01

      ret.lateralTuning.torque.kd = 0.0
      ret.lateralTuning.torque.deadzone = 0.0


    ret.steerRatio = 16.5
    ret.steerActuatorDelay = 0.1
    ret.steerRateCost = 0.4

    ret.steerLimitTimer = 2.5

    # longitudinal
    ret.longitudinalTuning.kpBP = [0., 5.*CV.KPH_TO_MS, 10.*CV.KPH_TO_MS, 30.*CV.KPH_TO_MS, 130.*CV.KPH_TO_MS]
    ret.longitudinalTuning.kpV = [1.25, 1.1, 1.0, 0.93, 0.52]
    ret.longitudinalTuning.kiBP = [0., 130. * CV.KPH_TO_MS]
    ret.longitudinalTuning.kiV = [0.1, 0.05]
    ret.longitudinalActuatorDelayLowerBound = 0.3
    ret.longitudinalActuatorDelayUpperBound = 0.3

    ret.stopAccel = -2.0
    ret.stoppingDecelRate = 0.4  # brake_travel/s while trying to stop
    ret.vEgoStopping = 0.5
    ret.vEgoStarting = 0.5

    # genesis
    if candidate == CAR.GENESIS:
      ret.mass = 1900. + STD_CARGO_KG
      ret.wheelbase = 3.01
      ret.centerToFront = ret.wheelbase * 0.4
      ret.maxSteeringAngleDeg = 90.
      ret.steerFaultMaxAngle = 0
    elif candidate == CAR.GENESIS_G70:
      ret.mass = 1640. + STD_CARGO_KG
      ret.wheelbase = 2.84
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.GENESIS_G80:
      ret.mass = 1855. + STD_CARGO_KG
      ret.wheelbase = 3.01
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.GENESIS_EQ900:
      ret.mass = 2200
      ret.wheelbase = 3.15
      ret.centerToFront = ret.wheelbase * 0.4

      # thanks to 파파
      ret.steerRatio = 16.0
      ret.steerActuatorDelay = 0.075
      ret.steerRateCost = 0.4

      if ret.lateralTuning.which() == 'torque':
        ret.lateralTuning.torque.useSteeringAngle = True
        max_lat_accel = 2.5
        ret.lateralTuning.torque.kp = 1.0 / max_lat_accel
        ret.lateralTuning.torque.kf = 1.0 / max_lat_accel
        ret.lateralTuning.torque.ki = 0.1 / max_lat_accel
        ret.lateralTuning.torque.friction = 0.01
        ret.lateralTuning.torque.kd = 0.0

    elif candidate == CAR.GENESIS_EQ900_L:
      ret.mass = 2290
      ret.wheelbase = 3.45
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.GENESIS_G90:
      ret.mass = 2150
      ret.wheelbase = 3.16
      ret.centerToFront = ret.wheelbase * 0.4
    # hyundai
    elif candidate in [CAR.SANTA_FE]:
      ret.mass = 1694 + STD_CARGO_KG
      ret.wheelbase = 2.766
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.SANTA_FE_2022, CAR.SANTA_FE_HEV_2022]:
      ret.mass = 1750 + STD_CARGO_KG
      ret.wheelbase = 2.766
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.SONATA, CAR.SONATA_HEV, CAR.SONATA21_HEV]:
      ret.mass = 1513. + STD_CARGO_KG
      ret.wheelbase = 2.84
      ret.centerToFront = ret.wheelbase * 0.4
      tire_stiffness_factor = 0.65
    elif candidate in [CAR.SONATA19, CAR.SONATA19_HEV]:
      ret.mass = 4497. * CV.LB_TO_KG
      ret.wheelbase = 2.804
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.SONATA_LF_TURBO:
      ret.mass = 1590. + STD_CARGO_KG
      ret.wheelbase = 2.805
      tire_stiffness_factor = 0.65
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.PALISADE:
      ret.mass = 1999. + STD_CARGO_KG
      ret.wheelbase = 2.90
      ret.centerToFront = ret.wheelbase * 0.4

      # thanks to 지구별(alexhys)
      ret.steerRatio = 16.0
      ret.steerActuatorDelay = 0.075
      ret.steerRateCost = 0.4

      if ret.lateralTuning.which() == 'torque':
        ret.lateralTuning.torque.useSteeringAngle = True
        max_lat_accel = 2.3
        ret.lateralTuning.torque.kp = 1.0 / max_lat_accel
        ret.lateralTuning.torque.kf = 1.0 / max_lat_accel
        ret.lateralTuning.torque.ki = 0.1 / max_lat_accel
        ret.lateralTuning.torque.friction = 0.0
        ret.lateralTuning.torque.kd = 0.1

    elif candidate in [CAR.ELANTRA, CAR.ELANTRA_GT_I30]:
      ret.mass = 1275. + STD_CARGO_KG
      ret.wheelbase = 2.7
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.ELANTRA_2021:
      ret.mass = (2800. * CV.LB_TO_KG) + STD_CARGO_KG
      ret.wheelbase = 2.72
      ret.steerRatio = 13.27 * 1.15   # 15% higher at the center seems reasonable
      tire_stiffness_factor = 0.65
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.ELANTRA_HEV_2021:
      ret.mass = (3017. * CV.LB_TO_KG) + STD_CARGO_KG
      ret.wheelbase = 2.72
      ret.steerRatio = 13.27 * 1.15  # 15% higher at the center seems reasonable
      tire_stiffness_factor = 0.65
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.KONA:
      ret.mass = 1275. + STD_CARGO_KG
      ret.wheelbase = 2.7
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.KONA_HEV, CAR.KONA_EV]:
      ret.mass = 1395. + STD_CARGO_KG
      ret.wheelbase = 2.6
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.IONIQ, CAR.IONIQ_EV_LTD, CAR.IONIQ_EV_2020, CAR.IONIQ_PHEV]:
      ret.mass = 1490. + STD_CARGO_KG
      ret.wheelbase = 2.7
      tire_stiffness_factor = 0.385
      #if candidate not in [CAR.IONIQ_EV_2020, CAR.IONIQ_PHEV]:
      #  ret.minSteerSpeed = 32 * CV.MPH_TO_MS
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.GRANDEUR_IG, CAR.GRANDEUR_IG_HEV]:
      tire_stiffness_factor = 0.8
      ret.mass = 1570. + STD_CARGO_KG
      ret.wheelbase = 2.845
      ret.centerToFront = ret.wheelbase * 0.385
      ret.steerRatio = 16.

    elif candidate in [CAR.GRANDEUR_IG_FL, CAR.GRANDEUR_IG_FL_HEV]:
      tire_stiffness_factor = 0.8
      ret.mass = 1600. + STD_CARGO_KG
      ret.wheelbase = 2.885
      ret.centerToFront = ret.wheelbase * 0.385
      ret.steerRatio = 17.
    elif candidate == CAR.VELOSTER:
      ret.mass = 3558. * CV.LB_TO_KG
      ret.wheelbase = 2.80
      tire_stiffness_factor = 0.9
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.TUCSON_TL_SCC:
      ret.mass = 1594. + STD_CARGO_KG #1730
      ret.wheelbase = 2.67
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    # kia
    elif candidate == CAR.SORENTO:
      ret.mass = 1985. + STD_CARGO_KG
      ret.wheelbase = 2.78
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.K5, CAR.K5_HEV]:
      ret.mass = 3558. * CV.LB_TO_KG
      ret.wheelbase = 2.80
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.K5_2021]:
      ret.mass = 3228. * CV.LB_TO_KG
      ret.wheelbase = 2.85
      tire_stiffness_factor = 0.7
    elif candidate == CAR.STINGER:
      tire_stiffness_factor = 1.125 # LiveParameters (Tunder's 2020)
      ret.mass = 1825.0 + STD_CARGO_KG
      ret.wheelbase = 2.906
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.FORTE:
      ret.mass = 3558. * CV.LB_TO_KG
      ret.wheelbase = 2.80
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.CEED:
      ret.mass = 1350. + STD_CARGO_KG
      ret.wheelbase = 2.65
      tire_stiffness_factor = 0.6
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.SPORTAGE:
      ret.mass = 1985. + STD_CARGO_KG
      ret.wheelbase = 2.78
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate in [CAR.NIRO_EV, CAR.NIRO_HEV, CAR.NIRO_HEV_2021]:
      ret.mass = 1737. + STD_CARGO_KG
      ret.wheelbase = 2.7
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.SELTOS:
      ret.mass = 1310. + STD_CARGO_KG
      ret.wheelbase = 2.6
      tire_stiffness_factor = 0.7
      ret.centerToFront = ret.wheelbase * 0.4
    elif candidate == CAR.MOHAVE:
      ret.mass = 2285. + STD_CARGO_KG
      ret.wheelbase = 2.895
      ret.centerToFront = ret.wheelbase * 0.5
      tire_stiffness_factor = 0.8
    elif candidate in [CAR.K7, CAR.K7_HEV]:
      tire_stiffness_factor = 0.7
      ret.mass = 1650. + STD_CARGO_KG
      ret.wheelbase = 2.855
      ret.centerToFront = ret.wheelbase * 0.4
      ret.steerRatio = 17.25
    elif candidate == CAR.K9:
      ret.mass = 2005. + STD_CARGO_KG
      ret.wheelbase = 3.15
      ret.centerToFront = ret.wheelbase * 0.4
      tire_stiffness_factor = 0.8

      ret.steerRatio = 14.5
      ret.steerRateCost = 0.4

      if ret.lateralTuning.which() == 'torque':
        ret.lateralTuning.torque.useSteeringAngle = True
        max_lat_accel = 2.5
        ret.lateralTuning.torque.kp = 1.0 / max_lat_accel
        ret.lateralTuning.torque.kf = 1.0 / max_lat_accel
        ret.lateralTuning.torque.ki = 0.1 / max_lat_accel
        ret.lateralTuning.torque.friction = 0.01
        ret.lateralTuning.torque.kd = 0.0


    ret.radarTimeStep = 0.05

    if ret.centerToFront == 0:
      ret.centerToFront = ret.wheelbase * 0.4


    # TODO: get actual value, for now starting with reasonable value for
    # civic and scaling by mass and wheelbase
    ret.rotationalInertia = scale_rot_inertia(ret.mass, ret.wheelbase)

    # TODO: start from empirically derived lateral slip stiffness for the civic and scale by
    # mass and CG position, so all cars will have approximately similar dyn behaviors
    ret.tireStiffnessFront, ret.tireStiffnessRear = scale_tire_stiffness(ret.mass, ret.wheelbase, ret.centerToFront,
                                                                         tire_stiffness_factor=tire_stiffness_factor)

    # no rear steering, at least on the listed cars above
    ret.steerRatioRear = 0.
    ret.steerControlType = car.CarParams.SteerControlType.torque

    ret.stoppingControl = True

    ret.enableBsm = 0x58b in fingerprint[0]
    ret.enableAutoHold = 1151 in fingerprint[0]

    # ignore CAN2 address if L-CAN on the same BUS
    ret.mdpsBus = 1 if 593 in fingerprint[1] and 1296 not in fingerprint[1] else 0
    ret.sasBus = 1 if 688 in fingerprint[1] and 1296 not in fingerprint[1] else 0
    ret.sccBus = 0 if 1056 in fingerprint[0] else 1 if 1056 in fingerprint[1] and 1296 not in fingerprint[1] \
                                                                     else 2 if 1056 in fingerprint[2] else -1

    if ret.sccBus >= 0:
      ret.hasScc13 = 1290 in fingerprint[ret.sccBus]
      ret.hasScc14 = 905 in fingerprint[ret.sccBus]

    ret.hasEms = 608 in fingerprint[0] and 809 in fingerprint[0]
    ret.hasLfaHda = 1157 in fingerprint[0]

    ret.radarOffCan = ret.sccBus == -1
    ret.pcmCruise = not ret.radarOffCan

    # set safety_hyundai_community only for non-SCC, MDPS harrness or SCC harrness cars or cars that have unknown issue
    if ret.radarOffCan or ret.mdpsBus == 1 or ret.openpilotLongitudinalControl or ret.sccBus == 1 or Params().get_bool('MadModeEnabled'):
      ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.hyundaiCommunity, 0)]
    return ret

  def _update(self, c: car.CarControl) -> car.CarState:
    pass

  def update(self, c: car.CarControl, can_strings: List[bytes]) -> car.CarState:
    self.cp.update_strings(can_strings)
    self.cp2.update_strings(can_strings)
    self.cp_cam.update_strings(can_strings)

    ret = self.CS.update(self.cp, self.cp2, self.cp_cam)
    ret.canValid = self.cp.can_valid and self.cp2.can_valid and self.cp_cam.can_valid
    ret.canTimeout = any(cp.bus_timeout for cp in self.can_parsers if cp is not None)

    if self.CP.pcmCruise and not self.CC.scc_live:
      self.CP.pcmCruise = False
    elif self.CC.scc_live and not self.CP.pcmCruise:
      self.CP.pcmCruise = True

    # most HKG cars has no long control, it is safer and easier to engage by main on

    if self.mad_mode_enabled:
      ret.cruiseState.enabled = ret.cruiseState.available

    # turning indicator alert logic
    if not self.CC.keep_steering_turn_signals and (ret.leftBlinker or ret.rightBlinker or self.CC.turning_signal_timer) and ret.vEgo < LANE_CHANGE_SPEED_MIN - 1.2:
      self.CC.turning_indicator_alert = True
    else:
      self.CC.turning_indicator_alert = False

    # low speed steer alert hysteresis logic (only for cars with steer cut off above 10 m/s)
    if ret.vEgo < (self.CP.minSteerSpeed + 0.2) and self.CP.minSteerSpeed > 10.:
      self.low_speed_alert = True
    if ret.vEgo > (self.CP.minSteerSpeed + 0.7):
      self.low_speed_alert = False

    buttonEvents = []
    if self.CS.cruise_buttons != self.CS.prev_cruise_buttons:
      be = car.CarState.ButtonEvent.new_message()
      be.pressed = self.CS.cruise_buttons != 0
      but = self.CS.cruise_buttons if be.pressed else self.CS.prev_cruise_buttons
      if but == Buttons.RES_ACCEL:
        be.type = ButtonType.accelCruise
      elif but == Buttons.SET_DECEL:
        be.type = ButtonType.decelCruise
      elif but == Buttons.GAP_DIST:
        be.type = ButtonType.gapAdjustCruise
      #elif but == Buttons.CANCEL:
      #  be.type = ButtonType.cancel
      else:
        be.type = ButtonType.unknown
      buttonEvents.append(be)
    if self.CS.cruise_main_button != self.CS.prev_cruise_main_button:
      be = car.CarState.ButtonEvent.new_message()
      be.type = ButtonType.altButton3
      be.pressed = bool(self.CS.cruise_main_button)
      buttonEvents.append(be)
    ret.buttonEvents = buttonEvents

    events = self.create_common_events(ret)

    if self.CC.longcontrol and self.CS.cruise_unavail:
      events.add(EventName.brakeUnavailable)
    #if abs(ret.steeringAngleDeg) > 90. and EventName.steerTempUnavailable not in events.events:
    #  events.add(EventName.steerTempUnavailable)
    if self.low_speed_alert and not self.CS.mdps_bus:
      events.add(EventName.belowSteerSpeed)
    if self.CC.turning_indicator_alert:
      events.add(EventName.turningIndicatorOn)

  # handle button presses
    for b in ret.buttonEvents:
      # do disable on button down
      if b.type == ButtonType.cancel and b.pressed:
        events.add(EventName.buttonCancel)
      if self.CC.longcontrol and not self.CC.scc_live:
        # do enable on both accel and decel buttons
        if b.type in [ButtonType.accelCruise, ButtonType.decelCruise] and not b.pressed:
          events.add(EventName.buttonEnable)
        if EventName.wrongCarMode in events.events:
          events.events.remove(EventName.wrongCarMode)
        if EventName.pcmDisable in events.events:
          events.events.remove(EventName.pcmDisable)
      elif not self.CC.longcontrol and ret.cruiseState.enabled:
        # do enable on decel button only
        if b.type == ButtonType.decelCruise and not b.pressed:
          events.add(EventName.buttonEnable)

    # scc smoother
    if self.CC.scc_smoother is not None:
      self.CC.scc_smoother.inject_events(events)

    ret.events = events.to_msg()

    self.CS.out = ret.as_reader()
    return self.CS.out

  # scc smoother - hyundai only
  def apply(self, c, controls):
    return self.CC.update(c, self.CS, controls)
