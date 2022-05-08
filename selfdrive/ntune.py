import os
import fcntl
import signal
import json
import weakref
from enum import Enum
import numpy as np

CONF_PATH = '/data/ntune/'
CONF_LAT_LQR_FILE = '/data/ntune/lat_lqr.json'
CONF_LAT_INDI_FILE = '/data/ntune/lat_indi.json'
CONF_LAT_TORQUE_FILE = '/data/ntune/lat_torque_v4.json'

ntunes = {}


def file_watch_handler(signum, frame):
  global ntunes
  for ntune in ntunes.values():
    ntune.handle()


class LatType(Enum):
  NONE = 0
  LQR = 1
  INDI = 2
  TORQUE = 3


class nTune():

  def get_ctrl(self):
    return self.ctrl() if self.ctrl is not None else None

  def __del__(self):
    if self.group is None:
      ntunes[self.key] = None
    print('__del__', self)

  def __init__(self, CP=None, ctrl=None, group=None):

    self.invalidated = False
    self.CP = CP
    self.ctrl = weakref.ref(ctrl) if ctrl is not None else None
    self.type = LatType.NONE
    self.group = group
    self.config = {}
    self.key = str(self)
    self.disable_lateral_live_tuning = CP.disableLateralLiveTuning if CP is not None else False

    if "LatControlLQR" in str(type(ctrl)):
      self.type = LatType.LQR
      self.file = CONF_LAT_LQR_FILE
      ctrl.A = np.array([0., 1., -0.22619643, 1.21822268]).reshape((2, 2))
      ctrl.B = np.array([-1.92006585e-04, 3.95603032e-05]).reshape((2, 1))
      ctrl.C = np.array([1., 0.]).reshape((1, 2))
      ctrl.K = np.array([-110., 451.]).reshape((1, 2))
      ctrl.L = np.array([0.33, 0.318]).reshape((2, 1))
    elif "LatControlTorque" in str(type(ctrl)):
      self.type = LatType.TORQUE
      self.file = CONF_LAT_TORQUE_FILE
    elif "LatControlINDI" in str(type(ctrl)):
      self.type = LatType.INDI
      self.file = CONF_LAT_INDI_FILE
    else:
      self.file = CONF_PATH + group + ".json"

    if not os.path.exists(CONF_PATH):
      os.makedirs(CONF_PATH)

    self.read()

    if self.group is None:
      ntunes[self.key] = self

    try:
      signal.signal(signal.SIGIO, file_watch_handler)
      fd = os.open(CONF_PATH, os.O_RDONLY)
      fcntl.fcntl(fd, fcntl.F_SETSIG, 0)
      fcntl.fcntl(fd, fcntl.F_NOTIFY, fcntl.DN_MODIFY | fcntl.DN_CREATE | fcntl.DN_MULTISHOT)
    except Exception as ex:
      print("exception", ex)
      pass

  def handle(self):
    try:
      if os.path.getsize(self.file) > 0:
        with open(self.file, 'r') as f:
          self.config = json.load(f)

        if self.checkValid():
          self.write_config(self.config)

        self.invalidated = True

    except:
      pass

  def check(self):  # called by LatControlLQR.update
    if self.invalidated:
      self.invalidated = False
      self.update()

  def read(self):
    success = False
    try:
      if os.path.getsize(self.file) > 0:
        with open(self.file, 'r') as f:
          self.config = json.load(f)

        if self.checkValid():
          self.write_config(self.config)

        self.update()
        success = True
    except:
      pass

    if not success:
      try:
        self.write_default()
        with open(self.file, 'r') as f:
          self.config = json.load(f)
          if self.checkValid():
            self.write_config(self.config)
          self.update()
      except:
        pass

  def checkValue(self, key, min_, max_, default_):
    updated = False

    if key not in self.config:
      self.config.update({key: default_})
      updated = True
    elif min_ > self.config[key]:
      self.config.update({key: min_})
      updated = True
    elif max_ < self.config[key]:
      self.config.update({key: max_})
      updated = True

    return updated

  def checkValid(self):

    if self.type == LatType.LQR:
      return self.checkValidLQR()
    elif self.type == LatType.INDI:
      return self.checkValidIndi()
    elif self.type == LatType.TORQUE:
      return self.checkValidTorque()
    elif self.group == "common":
      return self.checkValidCommon()
    else:
      return self.checkValidISCC()

  def update(self):

    if self.disable_lateral_live_tuning:
      return

    if self.type == LatType.LQR:
      self.updateLQR()
    elif self.type == LatType.INDI:
      self.updateIndi()
    elif self.type == LatType.TORQUE:
      self.updateTorque()

  def checkValidCommon(self):
    updated = False

    if self.checkValue("useLiveSteerRatio", 0., 1., 1.):
      updated = True

    if self.checkValue("steerRatio", 10.0, 20.0, 16.5):
      updated = True

    if self.checkValue("steerActuatorDelay", 0., 0.8, 0.1):
      updated = True

    if self.checkValue("steerRateCost", 0.1, 1.5, 0.4):
      updated = True

    if self.checkValue("pathOffset", -1.0, 1.0, 0.0):
      updated = True

    return updated

  def checkValidLQR(self):
    updated = False

    if self.checkValue("scale", 500.0, 5000.0, 1600.0):
      updated = True

    if self.checkValue("ki", 0.0, 0.2, 0.01):
      updated = True

    if self.checkValue("dcGain", 0.002, 0.004, 0.0025):
      updated = True

    if self.checkValue("steerLimitTimer", 0.5, 3.0, 2.5):
      updated = True

    return updated

  def checkValidIndi(self):
    updated = False

    if self.checkValue("actuatorEffectiveness", 0.5, 3.0, 1.8):
      updated = True
    if self.checkValue("timeConstant", 0.5, 3.0, 1.4):
      updated = True
    if self.checkValue("innerLoopGain", 1.0, 5.0, 3.3):
      updated = True
    if self.checkValue("outerLoopGain", 1.0, 5.0, 2.8):
      updated = True

    return updated

  def checkValidTorque(self):
    updated = False

    if self.checkValue("useSteeringAngle", 0., 1., 1.):
      updated = True
    if self.checkValue("maxLatAccel", 0.5, 4.0, 2.0):
      updated = True
    if self.checkValue("friction", 0.0, 0.2, 0.01):
      updated = True
    if self.checkValue("ki_factor", 0.0, 1.0, 0.1):
      updated = True
    if self.checkValue("kd", 0.0, 2.0, 0.0):
      updated = True
    if self.checkValue("deadzone", 0.0, 0.05, 0.0):
      updated = True

    return updated

  def checkValidISCC(self):
    updated = False

    if self.checkValue("sccGasFactor", 0.5, 1.5, 1.0):
      updated = True

    if self.checkValue("sccBrakeFactor", 0.5, 1.5, 1.0):
      updated = True

    if self.checkValue("sccCurvatureFactor", 0.5, 1.5, 0.98):
      updated = True

    return updated

  def updateLQR(self):
    lqr = self.get_ctrl()
    if lqr is not None:
      lqr.scale = float(self.config["scale"])
      lqr.ki = float(self.config["ki"])
      lqr.dc_gain = float(self.config["dcGain"])

      lqr.x_hat = np.array([[0], [0]])
      lqr.reset()

  def updateIndi(self):
    indi = self.get_ctrl()
    if indi is not None:
      indi._RC = ([0.], [float(self.config["timeConstant"])])
      indi._G = ([0.], [float(self.config["actuatorEffectiveness"])])
      indi._outer_loop_gain = ([0.], [float(self.config["outerLoopGain"])])
      indi._inner_loop_gain = ([0.], [float(self.config["innerLoopGain"])])
      indi.steer_filter.update_alpha(indi.RC)
      indi.reset()

  def updateTorque(self):
    torque = self.get_ctrl()
    if torque is not None:
      torque.use_steering_angle = float(self.config["useSteeringAngle"]) > 0.5
      max_lat_accel = float(self.config["maxLatAccel"])
      torque.pid._k_p = [[0], [1.0 / max_lat_accel]]
      torque.pid.k_f = 1.0 / max_lat_accel
      torque.pid._k_i = [[0], [self.config["ki_factor"] / max_lat_accel]]
      torque.pid._k_d = [[0], [float(self.config["kd"])]]
      torque.friction = float(self.config["friction"])
      torque.deadzone = float(self.config["deadzone"])
      torque.reset()

  def read_cp(self):

    try:
      if self.CP is not None:

        if self.type == LatType.LQR:
          self.config["scale"] = round(self.CP.lateralTuning.lqr.scale, 2)
          self.config["ki"] = round(self.CP.lateralTuning.lqr.ki, 3)
          self.config["dcGain"] = round(self.CP.lateralTuning.lqr.dcGain, 6)
        elif self.type == LatType.INDI:
          pass
        elif self.type == LatType.TORQUE:
          self.config["useSteeringAngle"] = 1. if self.CP.lateralTuning.torque.useSteeringAngle else 0.
          self.config["maxLatAccel"] = round(1. / self.CP.lateralTuning.torque.kp, 2)
          self.config["friction"] = round(self.CP.lateralTuning.torque.friction, 3)
          self.config["kd"] = round(self.CP.lateralTuning.torque.kd, 2)
          self.config["deadzone"] = round(self.CP.lateralTuning.torque.deadzone, 3)
        else:
          self.config["useLiveSteerRatio"] = 1.
          self.config["steerRatio"] = round(self.CP.steerRatio, 2)
          self.config["steerActuatorDelay"] = round(self.CP.steerActuatorDelay, 2)
          self.config["steerRateCost"] = round(self.CP.steerRateCost, 2)

    except:
      pass

  def write_default(self):

    try:
      self.read_cp()
      self.checkValid()
      self.write_config(self.config)
    except:
      pass

  def write_config(self, conf):
    try:
      with open(self.file, 'w') as f:
        json.dump(conf, f, indent=2, sort_keys=False)
        os.chmod(self.file, 0o666)
    except IOError:

      try:
        if not os.path.exists(CONF_PATH):
          os.makedirs(CONF_PATH)

        with open(self.file, 'w') as f:
          json.dump(conf, f, indent=2, sort_keys=False)
          os.chmod(self.file, 0o666)
      except:
        pass


def ntune_get(group, key):
  global ntunes
  if group not in ntunes:
    ntunes[group] = nTune(group=group)

  ntune = ntunes[group]

  if ntune.config == None or key not in ntune.config:
    ntune.read()

  v = ntune.config[key]

  if v is None:
    ntune.read()
    v = ntune.config[key]

  return v


def ntune_common_get(key):
  return ntune_get("common", key)


def ntune_common_enabled(key):
  return ntune_common_get(key) > 0.5


def ntune_scc_get(key):
  return ntune_get("scc", key)
