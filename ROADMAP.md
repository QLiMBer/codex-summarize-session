# Roadmap & Ideas

## Future Improvements
- Selection using pressing numbers, writing particular multi-digits IDs
- additional details (maybe including first few messages iot give use a hint?)
  - when selection using arrows
  - keyboard shortcut / menu
- Find (and summarize) the relevant previous sessions (based on cwd)?

- Sessions filtering
  - recent
  - selected date span
  - cwd based

- Test various ways of install, [browser] version with dependency in particular.

- Add automated tests covering message extraction, especially nested `response_item` payloads.


## Nice-to-Haves
- Publish the package to PyPI once ready to expose `pip install codex-summarize-session`.
  - Prepare PyPI metadata (project description, classifiers) and generate an API token.
  - Rehearse on TestPyPI (`twine upload --repository testpypi dist/*`) before pushing to the main index.
  - After publishing, verify with `pip install codex-summarize-session==<version>` in a fresh environment.

## Open Questions
- Should the interactive `SessionBrowser` live in its own module long term, or should shared helpers migrate elsewhere as more TUI features arrive?
- How do we want to verify both dependency setups (with/without `[browser]`) before release, and are the docs clear on that workflow?

## Development Notes
- Test both dependency setups when iterating on the browser: run once with `prompt_toolkit` installed (`python -m pip install .[browser]` or `pipx inject codex-summarize-session prompt_toolkit`) and again after uninstalling it (`python -m pip uninstall prompt_toolkit`) to ensure the CLI’s guidance for missing extras stays accurate.
