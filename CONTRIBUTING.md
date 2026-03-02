# Contributing

Thanks for your interest in contributing to YiMo!

## Development setup

Requirements:
- Python 3.12
- `uv`

```bash
uv sync --locked
uv run python main.py
```

## Running tests

```bash
uv run python -m unittest discover -s tests
```

## Code style

- Keep changes small and focused.
- Prefer clear naming over cleverness.
- Avoid introducing new dependencies unless necessary.

## Reporting bugs / feature requests

Please use GitHub Issues and include:
- OS + architecture
- YiMo version / commit
- Steps to reproduce
- Logs / screenshots if relevant (remove secrets)

## Security

If you believe you found a security issue, please follow `SECURITY.md`.

