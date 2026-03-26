# Semantic Versioning Policy

Aethermor follows [Semantic Versioning 2.0.0](https://semver.org/).

## Version Format

```
MAJOR.MINOR.PATCH
```

## What Each Component Means

### MAJOR (breaking)

Incremented when:
- Public API signatures change in incompatible ways
- Output formats change in ways that break downstream consumers
- Material database schema changes
- Energy model interface changes

### MINOR (feature)

Incremented when:
- New materials, paradigms, or cooling layers are added
- New analysis tools or capabilities are added
- New benchmark cases or validation suites are added
- Performance improvements with no output changes

### PATCH (fix)

Incremented when:
- Bug fixes that don't change the API
- Documentation corrections
- Dependency updates
- Gold output updates due to improved accuracy (documented in release notes)

## Pre-release Versions

Not currently used. All releases are production-stable.

## Version Locations

The canonical version is defined in `pyproject.toml`. These must all match:

- `pyproject.toml` `version` field
- GitHub release tag
- Wheel filename
- README install command
- RELEASE_NOTES filename

The `scripts/release_check.py` script verifies version consistency.

## Current Version

**1.0.0** — Production/Stable
