#!/usr/bin/env bash
# Run once `gh auth login` has access to the target org/account.
#
#   ./scripts/publish.sh <owner>/<repo>
#
# Creates the GitHub repo (public), pushes main + tags, builds a fresh
# Nomina.mcpb, and attaches it to a v1.0.0 release. Refuses to run if an
# existing 'origin' remote points anywhere other than <owner>/<repo>, so it
# never pushes this project to an unrelated remote.
set -euo pipefail

REPO="${1:?usage: scripts/publish.sh <owner>/<repo>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v gh >/dev/null || { echo "gh CLI not found." >&2; exit 1; }
gh auth status >/dev/null || { echo "Run 'gh auth login' first." >&2; exit 1; }

normalize_repo() {
  local url="${1%.git}"
  case "$url" in
    git@github.com:*) echo "${url#git@github.com:}" ;;
    ssh://git@github.com/*) echo "${url#ssh://git@github.com/}" ;;
    https://github.com/*) echo "${url#https://github.com/}" ;;
    *) echo "$url" ;;
  esac
}

if git remote get-url origin >/dev/null 2>&1; then
  EXISTING_URL="$(git remote get-url origin)"
  EXISTING_REPO="$(normalize_repo "$EXISTING_URL")"
  if [[ "${EXISTING_REPO,,}" != "${REPO,,}" ]]; then
    echo "Remote 'origin' is '$EXISTING_URL' (-> $EXISTING_REPO)," >&2
    echo "which does not match requested '$REPO'. Refusing to push to an" >&2
    echo "unrelated remote. Run 'git remote remove origin' first if you" >&2
    echo "intend to retarget this repo." >&2
    exit 1
  fi
  echo "Remote 'origin' already matches $REPO; pushing there."
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
