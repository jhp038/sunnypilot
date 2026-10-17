# Independent blind spot sound

Base: official sunnypilot `staging`, commit
`5fb421d045b6fd1f862886c00b1ad8ab939202bc` (v2026.003.000).
Feature branch: `feature/independent-bsm-alert`.

This staging snapshot includes `prebuilt` and a compiled `libparams_c.so`,
and omits the SCons build definitions. The existing binary does not contain
the new parameter key. Regenerate the native params library from the matching
full source/release build before enabling this feature. The code checks the
runtime key registry: an older binary keeps the feature off and disables the
toggle, rather than raising an unknown-key exception. No prebuilt artifacts
were patched or replaced, and removing `prebuilt` alone is insufficient for
this stripped snapshot.

## Enable and behavior

The **Independent Blind Spot Sound** toggle is in sunnypilot's Lane Change
settings. It defaults to **off** (`IndependentBsmAlert`, persistent and backed
up) and is available when the car reports BSM support. It does not depend on
the Auto Lane Change setting or steering/cruise engagement. Quiet Mode can
mute the advisory chime under the existing sound policy.

While onroad, exactly one active turn signal plus the corresponding
`carState.leftBlindspot` or `rightBlindspot` generates a single existing
`promptSingleHigh` chime. Both signals (hazard lights), opposite-side detections
and no signals do not generate warnings. No speed threshold is added.

A persistent hazardous condition produces one event, not repeated beeps.
The same side rearms after at least 0.5 seconds of continuously clear valid
input. Short BSM/signal dropouts do not rearm it. Changing the hazardous side
is a new condition. Turning the feature off or going offroad resets it.
Initialization, a newly received valid carState message, valid CAN and no CAN
timeout are required. Missing/invalid input suppresses and cancels pending
warnings, preserves the previous hazard latch and interrupts the clear timer.

## Alert architecture and priority

Ordinary `WARNING` events are not selected when disengaged and are cleared by
`SelfdriveD.update_alerts`. `PERMANENT` events are selected even when disabled;
this describes engagement eligibility, not infinite duration. The new
`OnroadEventSP.blindSpotWarning` is a one-shot `PERMANENT` event with the lowest
priority and a 0.3-second presentation window. That window permits soundd's
20 Hz subscriber to observe the event. Its existing sound has a single play
count. This is Honda-style trigger behavior, not an OEM Honda sound recording.

The existing AlertManager arbitrates and publishes `selfdriveState.alertSound`;
soundd plays it normally. Only this feature's pending alert entry is removed
if inputs cease to qualify or another alert wins arbitration. A suppressed
warning is consumed rather than queued for later playback. A higher-priority
alert preempts the BSM sound; it cannot cause the same BSM condition to beep
again afterward. No state-machine change or disengaged soundd bypass is used.

The only existing selfdrived changes read inputs/params, create an advisory
event and manage its pending presentation. Steering, longitudinal control,
CAN transmission, panda safety, BSM parsing and SecOC are unchanged. With the
toggle off, no BSM event is generated and existing alerts are unaffected.

## Limitations

This is supplementary information from sunnypilot's existing parsed BSM
signals. **Toyota 0x3F6 BSM data does not always match the OEM mirror indicator.
This feature is not a replacement for the factory BSM system.** It cannot
correct missing or inaccurate BSM data, and warnings can be muted, suppressed
by other alerts or missed when inputs are invalid. Check mirrors and traffic.

No installation or deployment to a car was performed. comma 4 audio output,
UI rendering and road behavior require validation in the normal target build;
the host tests do not establish those results.

## Validation

`test_blind_spot_warning.py` uses real simulated `CarState` messages and covers
the complete blinker/BSM truth table, long hazards, flicker, rearming, side
changes, offroad/disabled operation and invalid-data recovery.

`test_blind_spot_warning_integration.py` requires the normal sunnypilot build.
It covers disabled-state event eligibility, the single-play sound selection,
expiry without repeat, safety-alert preemption without delayed replay,
cancellation and generation gates without ALC/engagement dependencies.

Run from the repository root in the supported development environment:

```sh
pytest -q openpilot/sunnypilot/selfdrive/selfdrived/tests/test_blind_spot_warning.py
pytest -q openpilot/sunnypilot/selfdrive/selfdrived/tests/test_blind_spot_warning_integration.py
```
