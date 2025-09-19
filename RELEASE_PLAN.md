# Release Prep Checklist

## Quick TODO
- [ ] Update `pyproject.toml` version when ready.
- [ ] Commit and update `CHANGELOG.md`/`README.md` with latest changes.
- [ ] Build fresh artifacts with `python -m build` and run `twine check dist/*`.
- [ ] Smoke-test install from the built wheel in a clean environment.
- [ ] Tag the release and push (`git tag vX.Y.Z && git push origin vX.Y.Z`).
- [ ] Draft GitHub release notes (copy from `CHANGELOG.md`) and attach/mention artifacts.
- [ ] Optional: Upload artifacts to PyPI via `twine upload dist/*`.

## Step Details
- **Version bump**: edit `pyproject.toml` (and optionally expose `__version__`), then commit before building.
- **Docs/changelog**: ensure `README.md` usage examples reflect new behaviour; log the change in `CHANGELOG.md`.
- **Build artifacts**: run `rm -rf dist/ && python -m build`; verify `.tar.gz` and `.whl` files exist, then `twine check dist/*`.
- **Smoke-test**: use a clean env to `pip install dist/<wheel>` (or `pipx install dist/<wheel>`); run `codex-summarize-session list` and `extract` to confirm.
- **Tag & release**: `git tag vX.Y.Z`, `git push origin main`, `git push origin vX.Y.Z`; draft release notes via GitHub UI or `gh release create` referencing the changelog.
- **PyPI (optional)**: if publishing, configure credentials and `twine upload dist/*`; confirm `pip install codex-summarize-session==X.Y.Z` succeeds.
- **Post-release**: update badges/docs that mention the latest version and reopen the `Unreleased` section in `CHANGELOG.md` for future work.
