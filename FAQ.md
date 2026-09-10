
# FAQ — `ovos-simple-listener`

## What is `ovos-simple-listener`?
`ovos-simple-listener` is ovos-core listener daemon client.

## How do I install it?
```bash
pip install ovos-simple-listener
```
Or for development:
```bash
uv pip install -e .
```

## Where do I report bugs?
Open an issue on the GitHub repository. Ensure you are targeting the `dev` branch for fixes.

## How do I run tests?
```bash
uv run pytest test/ --cov=ovos_simple_listener
```

## How do I contribute?
1. Fork the repository and create a feature branch from `dev`.
2. Write tests for your changes.
3. Open a PR targeting the `dev` branch.
4. Ensure CI passes before requesting review.

## What Python versions are supported?
See `QUICK_FACTS.md` — currently `>=3.9`.
