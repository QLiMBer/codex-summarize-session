# Roadmap & Ideas

## Future Improvements
- Publish the package to PyPI once ready to expose `pip install codex-summarize-session`.
  - Prepare PyPI metadata (project description, classifiers) and generate an API token.
  - Rehearse on TestPyPI (`twine upload --repository testpypi dist/*`) before pushing to the main index.
  - After publishing, verify with `pip install codex-summarize-session==<version>` in a fresh environment.
- Explore a navigable session browser (arrow-key navigation, search filters).
- Add automated tests covering message extraction, especially nested `response_item` payloads.
- Consider packaging helper functions into a small library surface for scripting use.

## Nice-to-Haves
- CLI flag to export summaries in markdown/plaintext with minimal formatting.
- Integrate with an LLM summariser once API access and privacy constraints are resolved.
- Optional JSON output for the `list` command to support scripting.
