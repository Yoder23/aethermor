# Support Policy

## Supported Versions

| Version | Status | Support Level |
|---------|--------|---------------|
| 1.0.x | **Current** | Full support: bug fixes, security patches, documentation |
| 0.1.x | Retired | No support. Upgrade to 1.0.x. |

Only the latest release in each supported major.minor series receives updates.

## Reporting Issues

Use GitHub Issues with the appropriate template:

- **Bug report**: Something doesn't work as documented
- **Validation discrepancy**: A benchmark result doesn't match your expected value
- **Model question**: Uncertainty about whether a use case is in scope

See [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/) for templates.

## Response Expectations

| Issue Type | Target Response |
|------------|-----------------|
| Security vulnerability | 48 hours (see [SECURITY.md](../SECURITY.md)) |
| Bug report (validation failure) | 1 week |
| Bug report (other) | 2 weeks |
| Feature request | Best effort |
| Model question | Best effort |

## Deprecation Policy

- Features are deprecated with at least one minor version of warning
- Deprecated features emit `DeprecationWarning` at runtime
- Deprecated features are removed in the next major version
- Deprecations are documented in [CHANGELOG.md](../CHANGELOG.md)

## Breaking Changes

Breaking changes (API signature changes, output format changes, removed
features) only occur in major version bumps and are documented in the
release notes with migration guidance.
