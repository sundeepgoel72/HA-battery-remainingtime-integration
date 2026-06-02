# Calibration

Battery Remaining Time is designed to become increasingly accurate through calibration evidence gathered from normal battery operation.

## Calibration Anchors

The integration collects evidence from:

- Rest events
- Float events
- Absorption events
- Low battery events
- Heavy discharge events

## Persistent Evidence

Statistics survive Home Assistant restarts and are used to improve prediction quality.

Tracked statistics include:

- update_count
- calibration_anchor_events
- rest_events
- float_events
- absorption_events
- low_battery_events
- heavy_discharge_events

## Future Adaptive Learning

Future releases will learn:

- Actual battery capacity
- Charge efficiency
- Battery ageing
- Peukert exponent trends