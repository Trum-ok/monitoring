# Release and Versioning

This repository uses Semantic Versioning (`MAJOR.MINOR.PATCH`).

## Version policy

- `PATCH` (`0.1.1`) for bug fixes only.
- `MINOR` (`0.2.0`) for backward-compatible features.
- `MAJOR` (`1.0.0`) for breaking changes.

SDK version is defined in:

- `sdk/pyproject.toml` -> `[project].version`

## Release checklist (SDK)

1. Update `sdk/pyproject.toml` version.
2. Update `sdk/README.md` if public API changed.
3. Refresh the workspace lockfile and build the artifacts:

```bash
uv lock
uv build --package monitor-sdk
```

4. Commit changes:

```bash
git add sdk/pyproject.toml sdk/README.md uv.lock
git commit -m "release(sdk): vX.Y.Z"
```

5. Create git tag:

```bash
git tag -a sdk-vX.Y.Z -m "SDK release vX.Y.Z"
git push origin main --tags
```

6. Create GitHub Release from tag `sdk-vX.Y.Z` and attach changelog.

## Install SDK from GitHub

In client projects:

```bash
uv add "monitor-sdk @ git+https://github.com/<ORG>/<REPO>.git#subdirectory=sdk"
```

Pin to tag:

```bash
uv add "monitor-sdk @ git+https://github.com/<ORG>/<REPO>.git@sdk-vX.Y.Z#subdirectory=sdk"
```

Without uv:

```bash
pip install "git+https://github.com/<ORG>/<REPO>.git@sdk-vX.Y.Z#subdirectory=sdk"
```
