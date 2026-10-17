"""One-shot, advisory BSM warning independent of assistance engagement."""


class BlindSpotWarning:
  REARM_SECONDS = 0.5

  def __init__(self):
    self.hazard_side = 0
    self._alerted_side = 0
    self._clear_since = None

  def update(self, CS, *, enabled: bool, onroad: bool, data_valid: bool, now: float) -> bool:
    self.hazard_side = 0
    if not enabled or not onroad:
      self._alerted_side = 0
      self._clear_since = None
      return False

    # Missing/invalid samples neither create a hazard nor rearm a previous one.
    if not data_valid:
      self._clear_since = None
      return False

    if CS.leftBlinker != CS.rightBlinker:
      if CS.leftBlinker and CS.leftBlindspot:
        self.hazard_side = 1
      elif CS.rightBlinker and CS.rightBlindspot:
        self.hazard_side = 2

    if not self.hazard_side:
      if self._clear_since is None:
        self._clear_since = now
      return False

    rearmed = self._clear_since is not None and now - self._clear_since >= self.REARM_SECONDS
    self._clear_since = None
    if self.hazard_side != self._alerted_side or rearmed:
      self._alerted_side = self.hazard_side
      return True
    return False
