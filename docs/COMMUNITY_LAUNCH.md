# Community Launch Notes

Use this file when the repo is ready for a real public beta post. The goal is to attract field testers who actually run lead-acid batteries in Home Assistant, not generic stars.

## Best Channels

- Home Assistant Community forum
- HACS and custom-integration discussion spaces
- Inverter, solar backup, and off-grid Home Assistant groups
- Reddit communities focused on Home Assistant, solar, and self-hosted monitoring

## Suggested GitHub Topics

Add these repository topics from GitHub repo settings:

```text
home-assistant
hacs
custom-integration
battery
lead-acid
solar
inverter
ups
off-grid
energy-monitoring
sensor
recorder
```

## Beta Post Draft

Title:

```text
Lead-acid battery remaining-time estimator for Home Assistant
```

Body:

```text
I built a Home Assistant custom integration that estimates lead-acid battery state of charge, time to empty, and time to full from existing HA sensors.

It is aimed at inverter, solar backup, UPS, and off-grid systems where voltage alone is not enough to estimate real runtime.

It supports flooded, tubular, AGM, gel, and lead-carbon batteries. It can use voltage-only input, but works better with current or charge/load power sensors and Recorder history.

Current status: beta field validation. It is HACS-compatible as a custom repository.

Repository:
https://github.com/sundeepgoel72/HA-battery-remainingtime-integration

I am especially looking for testers who can compare the forecast against real inverter/runtime behaviour and report:
- battery type
- capacity and nominal voltage
- source sensors used
- whether current/power signs match expected charging/discharging direction
- where the forecast is useful or wrong
```

## Before Posting

- Add at least one Home Assistant screenshot.
- Add one real sensor example from a working inverter/battery setup.
- Tag a release matching `custom_components/battery_remaining_time/manifest.json`.
- Confirm HACS custom repository install on a live Home Assistant instance.
- Add the suggested GitHub topics.

## Useful Follow-Up Issues

Create tracking issues for:

- Screenshot set for HACS/custom repository install
- Field validation report template
- Known-good sensor examples by inverter brand/source integration
- HACS default repository readiness, if public adoption grows
