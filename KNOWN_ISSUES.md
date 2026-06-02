# Known Issues and Technical Debt

## Validation

- Limited real-world battery datasets
- Confidence model not yet field calibrated
- Limited chemistry-specific validation
- Live HACS UI install still needs end-user field confirmation even though metadata and HACS validation workflow are in place

## Algorithms

- KiBaM and Shepherd are implemented, but still need field validation across battery banks.
- Adaptive ensemble weighting is implemented with bounded learned weights, but confidence calibration still needs field data.

## Calibration

- Capacity learning is implemented and needs longer field validation.
- Charge efficiency learning is implemented and needs longer field validation.
- Peukert exponent learning is implemented and needs real discharge-cycle validation.
- Battery ageing estimation and profile optimization are implemented, but still need longer field validation before beta claims should be treated as final.

## Performance

- Recorder optimization still required
- Large history windows need benchmarking

## Documentation

- UI screenshots still need to be committed from a live Home Assistant frontend session
- Example dashboards pending
- HACS/public beta summary docs need periodic sync with actual shipped version/status

## Future Work

- Multi-battery support
- Battery bank support
- Additional chemistries
- Community-contributed battery profiles
