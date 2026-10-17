from itertools import product

import pytest
from opendbc.car.structs import car

from openpilot.sunnypilot.selfdrive.selfdrived.blind_spot_warning import BlindSpotWarning


def car_state(**kwargs):
  return car.CarState.new_message(canValid=True, **kwargs)


def update(warning, CS=None, now=0., **kwargs):
  args = {"enabled": True, "onroad": True, "data_valid": True, "now": now}
  args.update(kwargs)
  return warning.update(CS if CS is not None else car_state(), **args)


@pytest.mark.parametrize("left,right,left_bsm,right_bsm", list(product((False, True), repeat=4)))
def test_same_side_single_blinker_only(left, right, left_bsm, right_bsm):
  CS = car_state(leftBlinker=left, rightBlinker=right, leftBlindspot=left_bsm, rightBlindspot=right_bsm)
  expected = left != right and ((left and left_bsm) or (right and right_bsm))
  assert update(BlindSpotWarning(), CS) == expected


@pytest.mark.parametrize("side", ["left", "right"])
def test_persistent_hazard_and_flicker_do_not_repeat(side):
  warning = BlindSpotWarning()
  CS = car_state(**{f"{side}Blinker": True, f"{side}Blindspot": True})
  assert update(warning, CS)
  for frame in range(1, 1001):
    assert not update(warning, CS, now=frame * .01)
  assert not update(warning, now=10.01)
  assert not update(warning, CS, now=10.1)
  assert not update(warning, CS, now=11.)


@pytest.mark.parametrize("clear_state", [
  {}, {"leftBlinker": True}, {"leftBlinker": True, "rightBlinker": True, "leftBlindspot": True},
])
def test_rearm_after_continuously_clear_condition(clear_state):
  warning = BlindSpotWarning()
  CS = car_state(leftBlinker=True, leftBlindspot=True)
  assert update(warning, CS)
  assert not update(warning, car_state(**clear_state), now=.1)
  assert not update(warning, car_state(**clear_state), now=.5)
  assert update(warning, CS, now=.7)
  assert not update(warning, CS, now=.8)


def test_side_switch_is_a_new_condition():
  warning = BlindSpotWarning()
  assert update(warning, car_state(leftBlinker=True, leftBlindspot=True))
  assert update(warning, car_state(rightBlinker=True, rightBlindspot=True), now=.01)
  assert not update(warning, car_state(rightBlinker=True, rightBlindspot=True), now=.02)


@pytest.mark.parametrize("gate", ["enabled", "onroad"])
def test_disabled_or_offroad_resets(gate):
  warning = BlindSpotWarning()
  CS = car_state(leftBlinker=True, leftBlindspot=True)
  assert not update(warning, CS, **{gate: False})
  assert warning.hazard_side == 0
  assert update(warning, CS, now=.1)
  assert not update(warning, CS, now=.2, **{gate: False})
  assert warning.hazard_side == 0
  assert update(warning, CS, now=.3)


def test_invalid_data_does_not_create_or_rearm_hazard():
  warning = BlindSpotWarning()
  CS = car_state(leftBlinker=True, leftBlindspot=True)
  assert not update(warning, CS, data_valid=False)
  assert update(warning, CS, now=.1)
  assert not update(warning, now=.2)
  assert not update(warning, now=2., data_valid=False)
  assert warning.hazard_side == 0
  assert not update(warning, CS, now=3.)
  assert not update(warning, CS, now=4.)


def test_no_control_or_lane_change_state_required():
  # No control/ALC objects or parameters are consumed, even when cruise is off.
  CS = car_state(rightBlinker=True, rightBlindspot=True)
  CS.cruiseState.enabled = False
  assert update(BlindSpotWarning(), CS)
