# HACS Beta Hardening Checklist

This document tracks the hardening efforts required before public HACS beta release.

## Overview

The Battery Remaining Time integration is ready for a HACS beta release with some finalization items. This checklist consolidates the review across manifest.json, diagnostics, translations, entity names, unique IDs, and config flow.

---

## 1. Manifest.json Review

### Status: ✅ READY (Minor Enhancement)

**Current State:**
```json
{
  "domain": "battery_remaining_time",
  "name": "Battery Remaining Time",
  "codeowners": ["@sundeepgoel72"],
  "config_flow": true,
  "documentation": "https://github.com/sundeepgoel72/HA-battery-remainingtime-integration",
  "requirements": [],
  "version": "0.1.0"
}
```

**Findings:**
- ✅ Domain name is valid and follows HACS conventions
- ✅ Config flow is enabled
- ✅ Codeowner is properly set
- ✅ Documentation URL is correct
- ⚠️ **Missing version field** - should be included for tracking
- ⚠️ **Missing iot_class** - conflicting with hacs.json

**Recommended Changes:**

```json
{
  "domain": "battery_remaining_time",
  "name": "Battery Remaining Time",
  "codeowners": ["@sundeepgoel72"],
  "config_flow": true,
  "documentation": "https://github.com/sundeepgoel72/HA-battery-remainingtime-integration",
  "requirements": [],
  "version": "0.1.0",
  "iot_class": "local_polling",
  "homeassistant": "2024.6.0"
}
```

**Action Items:**
- [ ] Add `"version": "0.1.0"` field
- [ ] Add `"iot_class": "local_polling"` (matches hacs.json)
- [ ] Add `"homeassistant": "2024.6.0"` (minimum required version)

---

## 2. Entity Names & Unique IDs Review

### Status: ✅ READY

**Findings:**
- ✅ All sensor entity names are clearly defined in SENSOR_NAMES dict
- ✅ Unique IDs follow stable convention: `{entry.entry_id}_{key}`
- ✅ Suggested object IDs properly slugified using `_object_id()` helper
- ✅ Entity naming is consistent with Home Assistant conventions

**Sample Entity Structure:**
```
estimated_soc             → battery_estimated_soc (with device grouping)
time_to_empty             → battery_time_to_empty
time_to_full              → battery_time_to_full
learned_peukert_exponent  → battery_learned_peukert_exponent
algorithm_spread          → battery_algorithm_spread (diagnostic)
prediction_health         → battery_prediction_health (diagnostic)
calibration_status        → battery_calibration_status (diagnostic)
```

**Verified Features:**
- All sensors have unique_id set
- All sensors have suggested_object_id set
- Device info grouping is correct
- Diagnostic entities marked with EntityCategory.DIAGNOSTIC
- Entity names match strings.json definitions

---

## 3. Config Flow Review

### Status: ✅ READY

**Findings:**
- ✅ Config flow schema is well-structured
- ✅ Advanced options (power sensors, temperature) properly gated
- ✅ Selector components properly configured (entity, dropdown, number)
- ✅ Default values are sensible
- ✅ Unique ID generation is stable and deterministic

**Config Flow Steps:**
1. **Step: user** (initial setup)
   - Name
   - Algorithm (with options)
   - Battery type (with dropdown)
   - Capacity (Ah)
   - Nominal voltage (V)
   - Depletion voltage (V, optional)
   - Voltage sensor (required)
   - Current sensor (optional)
   - History window (minutes)
   - Update interval (seconds)

2. **Step: init** (options flow)
   - All fields from user step
   - Advanced fields unlocked:
     - Charge power sensor
     - Discharge power sensor
     - Temperature sensor

**Verified:**
- Unique ID generation prevents duplicate instances
- Schema supports both initial config and options editing
- Entity selectors properly scoped to sensor domain
- Number inputs have sensible min/max/step values

---

## 4. Strings/Translations Review

### Status: ✅ READY

**Findings:**
- ✅ strings.json is comprehensive
- ✅ All config flow fields have translations
- ✅ All entity names are translatable
- ⚠️ No language-specific translation files yet (out of scope for beta)

**Coverage:**
- Config flow: user step + options step
- Entity descriptions: 35+ sensors defined
- Issue descriptions: source_unavailable issue

**Sample Translations Available:**
```json
"estimated_soc": "Estimated SOC",
"time_to_empty": "Time to empty",
"learned_peukert_exponent": "Learned Peukert exponent",
"algorithm_spread": "Algorithm spread",
"prediction_health": "Prediction health",
"calibration_status": "Calibration status"
```

**Recommendation:**
- No action required for initial beta release
- Translation files (en.json, de.json, etc.) can be added in Phase 2

---

## 5. Diagnostics Review

### Status: ✅ READY

**Current Diagnostic Sensors:**

| Sensor | Key | Category | Purpose |
|--------|-----|----------|---------|
| Battery Health | `battery_health` | DIAGNOSTIC | Estimated health % |
| Learned Peukert Exponent | `learned_peukert_exponent` | DIAGNOSTIC | Adaptive learning result |
| Peukert Confidence | `peukert_confidence` | DIAGNOSTIC | Confidence level |
| Peukert Observation Count | `peukert_observation_count` | DIAGNOSTIC | Number of samples |
| Prediction Health | `prediction_health` | DIAGNOSTIC | Overall prediction quality |
| Calibration Status | `calibration_status` | DIAGNOSTIC | Evidence readiness % |
| Algorithm Spread | `algorithm_spread` | DIAGNOSTIC | Model divergence % |
| Model SOC Sensors | `soc_{model}` | DIAGNOSTIC | Per-model SOC comparison |

**Findings:**
- ✅ Diagnostic entities properly categorized
- ✅ Rich attributes provide context (confidence, observation counts, etc.)
- ✅ Prediction health sensor provides operational status summary
- ✅ Calibration status shows readiness for learning

**Diagnostic Attributes:**
Each diagnostic sensor includes comprehensive attributes:
- algorithm
- confidence
- confidence_score (0-100)
- algorithm_spread & stddev
- model_outputs (per-model SOC)
- calibration metrics
- event state information
- history window configuration

---

## 6. Home Assistant Compatibility

### Status: ⚠️ NEEDS MINOR FIXES

**Current hacs.json:**
```json
{
  "name": "Battery Remaining Time",
  "country": "IN",
  "render_readme": true,
  "homeassistant": "2024.6.0",
  "domains": ["sensor"],
  "iot_class": "Local Polling"
}
```

**Issues Found:**
- ✅ Minimum HA version specified (2024.6.0)
- ✅ Domains correctly set to sensor
- ✅ iot_class is set
- ⚠️ `iot_class` should be lowercase: `"local_polling"` (not "Local Polling")

**Recommendation:**
```json
{
  "name": "Battery Remaining Time",
  "country": "IN",
  "render_readme": true,
  "homeassistant": "2024.6.0",
  "domains": ["sensor"],
  "iot_class": "local_polling"
}
```

---

## 7. Documentation Completion

### Status: ⚠️ NEEDS ATTENTION

**Missing Documentation:**
- ❌ Screenshots of config flow
- ❌ Example dashboard configuration
- ❌ Sensor entity reference guide
- ❌ Battery profile examples

**Existing Documentation (✅):**
- README.md - Overview and features
- docs/ALGORITHMS.md - Algorithm details
- docs/BATTERY_TYPES.md - Battery chemistry profiles
- docs/CALIBRATION.md - Calibration engine details
- docs/ARCHITECTURE.md - System design
- docs/adaptive-peukert-learning.md - Peukert learning details

**Recommended New Files:**

### docs/SCREENSHOTS.md
```markdown
# Configuration Screenshots

## Setup Flow
1. [Config flow step 1 - name and algorithm]
2. [Config flow step 2 - battery type and capacity]
3. [Config flow step 3 - sensors configuration]

## Dashboard Example
[Dashboard showing estimated SOC, TTE, TTF, health metrics]
```

### docs/SENSOR_REFERENCE.md
```markdown
# Sensor Reference

## Main Sensors
- `sensor.estimated_soc` - Battery State of Charge
- `sensor.time_to_empty` - Hours until depleted
- `sensor.time_to_full` - Hours until fully charged

## Diagnostic Sensors (Optional)
[Complete reference for all 35+ sensors]
```

---

## 8. README Improvements

### Status: ⚠️ NEEDS MINOR UPDATES

**Current README:**
- ✅ Clear overview of integration purpose
- ✅ Feature list comprehensive
- ✅ Algorithm documentation
- ⚠️ Missing quick-start section
- ⚠️ Missing installation screenshot
- ⚠️ Missing dashboard screenshot
- ⚠️ Roadmap is vague (Phase 1-5)

**Recommended Additions:**

### Quick Start Section
```markdown
## Quick Start

1. **Add via HACS** (when beta available)
   - Go to Settings > Devices & Services > Custom Repositories
   - Add: https://github.com/sundeepgoel72/HA-battery-remainingtime-integration
   - Search for "Battery Remaining Time"
   - Install

2. **Configure Battery**
   - Go to Settings > Devices & Services > Create Integration
   - Select "Battery Remaining Time"
   - Choose algorithm (recommend Ensemble for first setup)
   - Select battery type
   - Provide capacity in Ah
   - Select voltage sensor from your Home Assistant

3. **View Sensors**
   - SOC: `sensor.battery_estimated_soc`
   - TTE: `sensor.battery_time_to_empty`
   - TTF: `sensor.battery_time_to_full`
```

### Dashboard Example
```markdown
## Example Dashboard

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Battery Status
    entities:
      - entity: sensor.estimated_soc
      - entity: sensor.time_to_empty
      - entity: sensor.time_to_full
      - entity: sensor.battery_health
      - entity: sensor.calibration_status
```

---

## 9. Release Checklist

### Pre-Release Validation
- [ ] All tests passing (target 80%+ coverage)
- [ ] No debug logging in production code
- [ ] All unique IDs validated
- [ ] Config flow tested with multiple battery types
- [ ] Manifest.json updated with version
- [ ] hacs.json: iot_class lowercase
- [ ] README: screenshots added
- [ ] Documentation: SENSOR_REFERENCE.md created
- [ ] No breaking changes from previous dev version
- [ ] Error handling tested (missing sensors, unavailable entities)

### Beta Release Notes Template
```markdown
# v0.1.0-beta.1 Release Notes

## Features
- Self-calibrating lead-acid battery prediction engine
- 10+ prediction algorithms (Ensemble as default)
- Adaptive Peukert exponent learning
- Battery health and lifecycle tracking
- 35+ diagnostic sensors

## Known Limitations
- Field validation in progress
- Confidence model requires real-world tuning
- KiBaM and Shepherd algorithms not yet implemented
- Multi-battery support planned for Phase 2

## Installation
Add via HACS as custom repository:
https://github.com/sundeepgoel72/HA-battery-remainingtime-integration

## Feedback
Please report issues and suggestions on GitHub.
```

---

## 10. Low-Risk Fixes

### Priority 1 (Do Before Beta)
- [ ] Update manifest.json with version and iot_class
- [ ] Fix hacs.json iot_class capitalization
- [ ] Add quick-start section to README
- [ ] Create docs/SENSOR_REFERENCE.md

### Priority 2 (Can Add During Beta)
- [ ] Add screenshots
- [ ] Add example dashboard YAML
- [ ] Create docs/SCREENSHOTS.md
- [ ] Expand roadmap with timeline

### Priority 3 (Post-Beta)
- [ ] Add multi-language translations
- [ ] Implement remaining algorithm models
- [ ] Add multi-battery support

---

## Sign-Off

**HACS Beta Readiness: 85% ✅**

The integration is substantially ready for HACS beta with minor documentation and configuration file updates. The codebase, config flow, diagnostics, and entity structure are solid.

**Blocking Items:** None

**Recommended Items Before Release:**
1. Update manifest.json (5 min)
2. Fix hacs.json (2 min)
3. Add quick-start to README (10 min)
4. Create SENSOR_REFERENCE.md (20 min)

**Total Time to Beta-Ready:** ~40 minutes

---

## Timeline Suggestion

- **Day 1:** Apply configuration fixes, README updates
- **Day 2:** Create sensor documentation
- **Day 3:** Screenshot collection and dashboard examples
- **Day 4:** Final review and beta release

**Target: Beta Release within 1 week**

---

## Next Actions

1. **This Sprint:** Apply manifest/hacs fixes + README updates
2. **Next Sprint:** Add comprehensive sensor documentation
3. **Post-Beta:** Field validation and Ensemble weighting adaptive learning
