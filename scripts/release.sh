#!/usr/bin/env bash
# Cut a release from a clean, committed version bump:
#
#   ./scripts/release.sh <version>
#
# Order matters: build the bundle, hash it, commit the hash into server.json, tag,
# push, create the GitHub release with the bundle attached, publish to the MCP
# Registry, then confirm the registry serves the new version. The committed
# server.json therefore always references an asset that exists.
set -euo pipefail

VERSION="${1:?usage: scripts/release.sh <version>}"
TAG="v$VERSION"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for tool in gh jq shasum uv mcp-publisher; do
  command -v "$tool" >/dev/null || { echo "$tool not found on PATH." >&2; exit 1; }
done
gh auth status >/dev/null || { echo "Run 'gh auth login' first." >&2; exit 1; }

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean; commit the version bump first." >&2
  exit 1
fi
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "Tag $TAG already exists." >&2
  exit 1
fi
NOTES="docs/announcements/$TAG.md"
[[ -f "$NOTES" ]] || { echo "Release notes $NOTES are missing." >&2; exit 1; }

uv sync --frozen
uv run --frozen ruff check .
uv run --frozen pytest -q
uv run --frozen python scripts/build_bundle.py

BUILT_VERSION="$(jq -r .version server.json)"
if [[ "$BUILT_VERSION" != "$VERSION" ]]; then
  echo "server.json is at $BUILT_VERSION, not $VERSION; bump and commit first." >&2
  exit 1
fi
# Schema-check registry metadata (field lengths, identifiers) before any push or tag;
# the sha placeholder is already a valid hash string, so this is complete apart from it.
mcp-publisher validate

SHA="$(shasum -a 256 dist/Nomina.mcpb | cut -d' ' -f1)"
jq --arg sha "$SHA" '.packages[0].fileSha256 = $sha' server.json > server.json.tmp
mv server.json.tmp server.json
if [[ -n "$(git status --porcelain -- server.json)" ]]; then
  git commit -q -m "chore: release $TAG" -- server.json
fi

git tag "$TAG"
git push origin main --tags

gh release create "$TAG" dist/Nomina.mcpb --title "Nomina $TAG" --notes-file "$NOTES"

# Registry JWTs live five minutes; log in immediately before publishing.
mcp-publisher login github --token "$(gh auth token)"
mcp-publisher publish

PUBLISHED="$(curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.nomina-xyz/nomina-mcp" \
  | jq -r '.servers[].server.version')"
if ! grep -qx "$VERSION" <<<"$PUBLISHED"; then
  echo "Registry does not list $VERSION yet; it lists: $PUBLISHED" >&2
  exit 1
fi
echo "Released Nomina $TAG (sha256 $SHA)."
