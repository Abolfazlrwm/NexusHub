# Contributing to NexusHub

Thanks for your interest in improving NexusHub. This document covers the
development setup, branch and commit conventions, and the pull-request
checklist.

## Prerequisites

- Python 3.10+ (3.12 recommended)
- `pip` ≥ 21
- (later milestones) Node.js 20+ and Docker for the platform apps

## Setup

```bash
git clone https://github.com/Abolfazlrwm/NexusHub.git
cd NexusHub
pip install -e "packages/nexusagent[dev]"
```

Run all checks locally before opening a PR:

```bash
make check       # ruff + mypy + pytest
# or individually
make lint typecheck test
```

## Branch naming

- `feat/<area>-<short-description>` — features (e.g. `feat/engine-memory`)
- `fix/<area>-<short-description>` — bug fixes
- `docs/…`, `chore/…`, `refactor/…` — everything else

Areas: `engine`, `api`, `dashboard`, `rag`, `eval`, `infra`.

## Commit messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <imperative summary>

<optional body: motivation, trade-offs, what changed and why>
```

- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `perf`
- Scopes: `engine`, `api`, `dashboard`, `rag`, `eval` — or none for repo-wide changes
- Keep commits small and self-contained: one logical change per commit

## Pull requests

- Target `main`; feature branches are merged with `--no-ff`
- Add or adjust tests for every behaviour change
- All CI checks (ruff, mypy, pytest) must pass
- Update docs / README when behaviour or public APIs change

## Code style

- Formatting and lint rules are enforced by `ruff` (line length 100)
- Type annotations everywhere under `src/`; `mypy` must pass
- Docstrings for every public module, class and function
- The engine must never call `eval()`/`exec()` on model-controlled input —
  see the calculator tool for the safe AST-based pattern

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
