# Known Issues and Technical Debt

## Validation

- Limited real-world battery datasets
- Spread-based confidence model still needs field calibration
- Limited chemistry-specific validation
- Live HACS UI install still needs end-user field confirmation even though metadata and HACS validation workflow are in place

## Critical Field Defects

- Issue #17 triggered a real field failure where ensemble SOC collapsed from high SOC to `0%` while `algorithm_spread` was extreme and confidence remained high.
- The likely cause was a rogue per-algorithm SOC output combined with mean-style ensemble sensitivity, weak confidence gating, and calibration-anchor acceptance during untrusted predictions.
- Local mitigation is now implemented:
  - robust median ensemble aggregation
  - spread-based confidence with `very_low`
  - SOC rate limiting
  - last-valid-SOC preservation when source evidence degrades
  - calibration-anchor blocking on low trust / fallback evidence
- Remaining risk: the exact rogue source model still needs live field confirmation.

- Issue #18 required per-algorithm observability. Comparison sensors and per-update debug logging are implemented, pushed, and deployed into the local HA instance. Remaining work is longer field verification and UI review of the new entity surface.

## Algorithms

- KiBaM and Shepherd are implemented, but still need field validation across battery banks.
- Adaptive ensemble weighting is implemented with bounded learned weights, but spread/confidence thresholds still need field data.

## Calibration

- Capacity learning is implemented and needs longer field validation.
- Charge efficiency learning is implemented and needs longer field validation.
- Peukert exponent learning is implemented and needs real discharge-cycle validation.
- Battery ageing estimation and profile optimization are implemented, but still need longer field validation before beta claims should be treated as final.

## Performance

- Recorder optimization still required
- Large history windows need benchmarking

## Documentation

- README, Quick Start, sensor reference, and handover must track the temporary re-expanded comparison-sensor surface during beta debugging.
- UI screenshots still need to be committed from a live Home Assistant frontend session
- Example dashboards pending
- HACS/public beta summary docs need periodic sync with actual shipped version/status

## Future Work

- Multi-battery support
- Battery bank support
- Additional chemistries
- Community-contributed battery profiles
