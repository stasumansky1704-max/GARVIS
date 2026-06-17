# Activating orchestrator CI

The CI definition lives here at `runtime/orchestrator/ci/orchestrator.yml`. It is **not**
auto-installed under `.github/workflows/` because the push token used in this environment
lacks the GitHub `workflow` scope (GitHub rejects pushes that add/modify workflow files
without it). This is a token-scope limitation, not a safety issue.

## Option A — activate as GitHub Actions (recommended)
With a token/user that has the `workflow` scope:

```bash
mkdir -p .github/workflows
cp runtime/orchestrator/ci/orchestrator.yml .github/workflows/orchestrator.yml
git add .github/workflows/orchestrator.yml
git commit -m "ci: activate orchestrator workflow"
git push
```

The workflow then runs py_compile + `verify` + secret-scan + all offline suites + a safe
CLI smoke on every push/PR that touches `runtime/orchestrator/**` or `tests/**`. It never
starts the backend, Docker, GPU runtime, or dashboard, and never runs audio or live PR
actions.

## Option B — executable local fallback (works today, no scope needed)
Run the exact same checks locally / in any runner, in-process (no subprocess):

```bash
python runtime/orchestrator/cli.py ci-check
```

`ci-check` performs: py_compile of the agent core → `verify` (6 safety checks) →
secret-scan → all offline test suites, and exits non-zero on any failure. Use it as a
pre-push gate until Option A is installed.
