# ORI-C workflow cleanup

This cleanup removes the generic maintainer workflows that were added too early and made the Actions tab unreadable.

Files removed if present:

- `.github/workflows/codeql.yml`
- `.github/workflows/dependency-review.yml`
- `.github/workflows/secrets.yml`
- `.github/workflows/docs.yml`
- `.github/workflows/release.yml`
- `.github/workflows/coverage.yml`
- `.github/workflows/package.yml`
- `.github/dependency-review-config.yml`
- `docs/MAINTAINERS_WORKFLOWS.md`
- `docs/PYTHON_SUPPORT.md`

The script does not remove the original ORI-C workflows:

- `ci.yml`
- `collector.yml`
- `nightly.yml`
- `qcc_canonical_full.yml`
- `sector_pilots.yml`

It also does not remove `.github/dependabot.yml`, because that file was already present in the uploaded repository snapshot.
