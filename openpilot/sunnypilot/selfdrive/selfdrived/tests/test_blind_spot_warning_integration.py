"""Requires the normal sunnypilot native build (params, msgq, etc.)."""
from types import SimpleNamespace

import pytest

from opendbc.car.structs import car
from openpilot.cereal import custom
from openpilot.selfdrive.selfdrived.alertmanager import AlertManager
from openpilot.selfdrive.selfdrived.selfdrived import SelfdriveD
from openpilot.selfdrive.selfdrived.state import StateMachine
from openpilot.selfdrive.selfdrived.events import Events
from openpilot.sunnypilot.selfdrive.selfdrived.events import EventsSP
from openpilot.sunnypilot.selfdrive.selfdrived.events_base import Alert, ET, Priority, AlertSize, AlertStatus, VisualAlert, AudibleAlert
from openpilot.sunnypilot.selfdrive.selfdrived.blind_spot_warning import BlindSpotWarning


BSM_TYPE = "blindSpotWarning/permanent"


def make_selfdrived():
  sd = SelfdriveD.__new__(SelfdriveD)
  sd.AM = AlertManager()
  sd.events = Events()
  sd.events_sp = EventsSP()
  sd.state_machine = StateMachine()  # disengaged: PERMANENT only
  sd.enabled = False
  sd.CP = car.CarParams.new_message(enableBsm=True)
  sd.sm = SimpleNamespace(frame=0)
  sd.is_metric = True
  sd.personality = 1
  sd.blind_spot_warning = BlindSpotWarning()
  return sd


def trigger(sd, CS, frame=0):
  sd.sm.frame = frame
  sd.events_sp.clear()
  if sd.blind_spot_warning.update(CS, enabled=True, onroad=True, data_valid=True, now=frame * .01):
    sd.events_sp.add(custom.OnroadEventSP.EventName.blindSpotWarning)
  sd.update_alerts(CS)


def test_disengaged_permanent_alert_uses_existing_sound_enum():
  sd = make_selfdrived()
  CS = car.CarState.new_message(leftBlinker=True, leftBlindspot=True)
  trigger(sd, CS)
  assert sd.AM.current_alert.alert_type == BSM_TYPE
  assert sd.AM.current_alert.audible_alert == custom.SelfdriveStateSP.AudibleAlert.promptSingleHigh
  assert not sd.enabled
  for frame in range(1, 100):
    trigger(sd, CS, frame)
  assert sd.AM.current_alert.alert_type != BSM_TYPE
  assert not sd.events_sp.names


@pytest.mark.parametrize("safety_frame", [0, 1])
def test_safety_alert_preempts_and_drops_bsm_without_late_replay(safety_frame):
  sd = make_selfdrived()
  CS = car.CarState.new_message(leftBlinker=True, leftBlindspot=True)
  if safety_frame:
    trigger(sd, CS)
  safety = Alert("Safety", "", AlertStatus.critical, AlertSize.full, Priority.HIGHEST,
                 VisualAlert.none, AudibleAlert.warningImmediate, .05)
  safety.alert_type = "testSafety/permanent"
  safety.event_type = ET.PERMANENT
  sd.AM.add_many(safety_frame, [safety])
  trigger(sd, CS, safety_frame)
  assert sd.AM.current_alert is safety
  assert BSM_TYPE not in sd.AM.alerts
  for frame in range(safety_frame + 1, 50):
    trigger(sd, CS, frame)
    assert sd.AM.current_alert.alert_type != BSM_TYPE


def test_hazards_cancel_pending_alert():
  sd = make_selfdrived()
  CS = car.CarState.new_message(leftBlinker=True, leftBlindspot=True)
  trigger(sd, CS)
  CS.rightBlinker = True
  trigger(sd, CS, 1)
  assert BSM_TYPE not in sd.AM.alerts
  assert sd.AM.current_alert.alert_type != BSM_TYPE


def test_feature_off_preserves_existing_alert():
  sd = make_selfdrived()
  CS = car.CarState.new_message(leftBlinker=True, leftBlindspot=True)
  existing = Alert("Existing", "", AlertStatus.normal, AlertSize.small, Priority.LOW,
                   VisualAlert.none, AudibleAlert.prompt, 1.)
  existing.alert_type = "existing/permanent"
  existing.event_type = ET.PERMANENT
  sd.AM.add_many(0, [existing])
  assert not sd.blind_spot_warning.update(CS, enabled=False, onroad=True, data_valid=True, now=0.)
  sd.update_alerts(CS)
  assert sd.AM.current_alert is existing
  assert not sd.events_sp.names


@pytest.mark.parametrize("gate", ["enabled", "onroad", "data_valid"])
def test_ineligible_input_cancels_pending_notification(gate):
  sd = make_selfdrived()
  CS = car.CarState.new_message(rightBlinker=True, rightBlindspot=True)
  trigger(sd, CS)
  sd.events_sp.clear()
  args = {"enabled": True, "onroad": True, "data_valid": True, "now": .01}
  args[gate] = False
  assert not sd.blind_spot_warning.update(CS, **args)
  sd.sm.frame = 1
  sd.update_alerts(CS)
  assert BSM_TYPE not in sd.AM.alerts


@pytest.mark.parametrize("gate", [None, "featureOff", "offroad", "uninitialized", "missingCarState", "invalidCan", "canTimeout", "noBsm"])
def test_event_generation_is_independent_of_passive_and_alc(gate):
  sd = make_selfdrived()
  sd.CP.passive = True
  sd.sm = {"deviceState": SimpleNamespace(started=gate != "offroad")}
  sd.independent_bsm_alert = gate != "featureOff"
  sd.initialized = gate != "uninitialized"
  sd.car_state_valid = gate != "missingCarState"
  sd.CP.enableBsm = gate != "noBsm"
  CS = car.CarState.new_message(canValid=True, leftBlinker=True, leftBlindspot=True)
  CS.canValid = gate != "invalidCan"
  CS.canTimeout = gate == "canTimeout"
  sd.update_blind_spot_warning(CS)
  assert (custom.OnroadEventSP.EventName.blindSpotWarning in sd.events_sp.names) == (gate is None)
