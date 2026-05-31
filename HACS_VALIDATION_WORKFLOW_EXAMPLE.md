# HACS Validation Workflow

Create:

.github/workflows/hacs.yml

Example:

```yaml
name: HACS Validation

on:
  push:
  pull_request:

jobs:
  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
```
