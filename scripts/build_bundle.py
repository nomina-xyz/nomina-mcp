"""Build the portable Claude Desktop extension and a local stdio config alternative.

Run with: uv run python scripts/build_bundle.py
"""

import hashlib
import json
import re
import shutil
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILES = (
    "manifest.json",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "server.py",
    "nomina/__init__.py",
    "nomina/server.py",
    "nomina/market.py",
    "icon.png",
)
_PACKAGE_IDENTIFIERS = {
    "mcpb": "https://github.com/nomina-xyz/nomina-mcp/releases/download/v{}/Nomina.mcpb",
    "oci": "ghcr.io/nomina-xyz/nomina-mcp:{}",
}


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def check_versions() -> str:
    """Return the single release version, or exit naming every out-of-step file."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    server = _json("server.json")
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    init_source = (ROOT / "nomina" / "__init__.py").read_text()
    init_match = re.search(r'^__version__ = "(.+)"$', init_source, re.MULTILINE)
    versions = {
        "manifest.json": _json("manifest.json")["version"],
        "pyproject.toml": project["project"]["version"],
        "uv.lock": next(
            (p["version"] for p in lock["package"] if p["name"] == project["project"]["name"]),
            None,
        ),
        "server.json": server["version"],
        "server.json.packages[0]": server["packages"][0]["version"],
        "gemini-extension.json": _json("gemini-extension.json")["version"],
        "plugin.json": _json("plugin.json")["version"],
        "nomina/__init__.py": init_match.group(1) if init_match else None,
    }
    if len(set(versions.values())) != 1:
        raise SystemExit(
            "Version mismatch: " + ", ".join(f"{name}={value}" for name, value in versions.items())
        )
    version = versions["pyproject.toml"]
    for index, package in enumerate(server["packages"]):
        expected = _PACKAGE_IDENTIFIERS[package["registryType"]].format(version)
        if package["identifier"] != expected:
            raise SystemExit(
                f"server.json packages[{index}].identifier must be {expected}, "
                f"got {package['identifier']}"
            )
    return version


def main() -> None:
    check_versions()
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("Install uv before building the bundle.")
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    bundle = destination / "Nomina.mcpb"
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in BUNDLE_FILES:
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, (ROOT / name).read_bytes())
    config = {
        "mcpServers": {
            "nomina": {
                "command": str(Path(uv).resolve()),
                "args": ["run", "--frozen", "--no-dev", "--directory", str(ROOT), "server.py"],
            }
        }
    }
    (destination / "claude_desktop_config.json").write_text(json.dumps(config, indent=2) + "\n")
    print(f"Built {bundle} ({bundle.stat().st_size:,} bytes)")
    print(f"sha256  {hashlib.sha256(bundle.read_bytes()).hexdigest()}")
    print(f"Alternative local launch config: {destination / 'claude_desktop_config.json'}")


if __name__ == "__main__":
    main()
