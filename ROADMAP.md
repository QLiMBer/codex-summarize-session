# Roadmap & Ideas

## Future Improvements
- Explore a navigable session browser (arrow-key navigation, search filters).
- Add automated tests covering message extraction, especially nested `response_item` payloads.
- Selection using pressing numbers, writing particular multi-digits IDs
- additional details
  - when selection using arrows
  - keyboard shortcut / menu
- Find and summarize the relevant previous sessions (based on cwd)?

## Nice-to-Haves
- Publish the package to PyPI once ready to expose `pip install codex-summarize-session`.
  - Prepare PyPI metadata (project description, classifiers) and generate an API token.
  - Rehearse on TestPyPI (`twine upload --repository testpypi dist/*`) before pushing to the main index.
  - After publishing, verify with `pip install codex-summarize-session==<version>` in a fresh environment.