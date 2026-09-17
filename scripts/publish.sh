#!/usr/bin/env bash
# Run once `gh auth login` has access to the target org/account.
#
#   ./scripts/publish.sh <owner>/<repo>
#
# Creates the GitHub repo (public), pushes main + tags, builds a fresh
# Nomina.mcpb, and attaches it to a v1.0.0 release. Safe to re-run: repo
# creation and the push are idempotent if the repo already exists; the
# release step will fail loudly instead of silently overwriting one.
set -euo pipefail

REPO="${1:?usage: scripts/publish.sh <owner>/<repo>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v gh >/dev/null || { echo "gh CLI not found." >&2; exit 1; }
gh auth status >/dev/null || { echo "Run 'gh auth login' first." >&2; exit 1; }

if git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' already set to $(git remote get-url origin); pushing there."
else
  gh repo create "$REPO" --public --source=. --remote=origin
fi

git push -u origin main --tags

uv sync --frozen
uv run --frozen ruff check .
uv run --frozen pytest -q
uv run --frozen python scripts/build_bundle.py

gh release create v1.0.0 dist/Nomina.mcpb \
  --repo "$REPO" \
  --title "Nomina v1.0.0" \
  --notes "Markets research for agents. Three read-only tools over Yahoo Finance, no API key.
Install: Claude Desktop -> Settings -> Extensions -> Advanced settings -> Install Extension -> Nomina.mcpb.
See README for data-source limits and branding provenance."

echo "Published $REPO @ v1.0.0."
