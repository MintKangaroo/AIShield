# Contributing

Use Python 3.11 or 3.12 and Node.js 22. Keep changes typed, tested, documented, and limited to one
roadmap milestone.

## Branch policy

| Branch | Purpose |
| --- | --- |
| `main` | Always runnable, tested stable release |
| `develop` | Integration branch for the next release |
| `feat/<feature-name>` | One feature developed from `develop` |
| `fix/<issue-name>` | One bug fix |
| `docs/<document-name>` | Documentation-only change |

Feature, fix, and documentation branches merge into `develop` after their quality gates pass.
Release changes move from `develop` to `main` only after the full CPU demo is healthy. Do not commit
unfinished feature work directly to `main`.

Run backend quality gates in an activated environment:

```bash
python -m pip install torch==2.13.0 torchvision==0.28.0 \
  --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,ml]"
make check
```

Run dashboard and Compose checks separately:

```bash
npm --prefix web ci
npm --prefix web run check
npm --prefix web run build
make compose-check
```

Use Conventional Commits. Changes to numerical attacks require independent numerical tests for
gradient direction, perturbation bounds, clamp behavior, and parameter validation. Changes to result
contracts require regenerated JSON Schema and backward-compatibility review.

Never commit `.env`, credentials, tokens, raw datasets, model weights, generated adversarial
examples, or experiment artifacts. Public dataset adapters must use a reviewed canonical source and
checksum rather than a caller-supplied URL.
