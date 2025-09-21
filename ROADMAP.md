# Roadmap & Ideas

## Future Improvements
- Interactive session browser (arrow-key navigation, search filters).
- Selection using pressing numbers, writing particular multi-digits IDs
- additional details (maybe including first few messages iot give use a hint?)
  - when selection using arrows
  - keyboard shortcut / menu
- Find (and summarize) the relevant previous sessions (based on cwd)?

- Add automated tests covering message extraction, especially nested `response_item` payloads.


## Nice-to-Haves
- Publish the package to PyPI once ready to expose `pip install codex-summarize-session`.
  - Prepare PyPI metadata (project description, classifiers) and generate an API token.
  - Rehearse on TestPyPI (`twine upload --repository testpypi dist/*`) before pushing to the main index.
  - After publishing, verify with `pip install codex-summarize-session==<version>` in a fresh environment.