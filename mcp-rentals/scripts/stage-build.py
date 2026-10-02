"""Create a minimal, auditable Docker context from trusted local sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PROVIDER_LAYOUTS = {
    "alecorretoramg": ("src", "scripts"), "arthusoimoveis": ("arthuso", "scripts"), "cabralporto": ("src", "scripts"),
    "casalinhares": ("scripts",), "epifanioimoveis": ("src", "scripts"), "helenaimoveis": ("src", "scripts"),
    "imobiliariaportalmg": ("src", "scripts"), "imobiliariavaleinvest": ("src", "scripts"),
    "imovelweb": ("src", "scripts"), "marcioimoveis": ("src", "scripts"),
    "minascaixaimoveis": ("minascaixa", "scripts"), "niltoncorretordeimoveis": ("src", "scripts"),
    "novaimobiliaria": ("src", "scripts"), "veraimobiliaria": ("src", "scripts"), "vivareal": ("src", "scripts"),
}
ALLOWED_SUFFIXES = {".cfg", ".css", ".html", ".ini", ".json", ".py", ".toml", ".ts", ".txt", ".typed", ".xml", ".yaml", ".yml"}
STAGING_MARKER = ".mcp-rentals-build-context"
SENSITIVE_PATTERN = re.compile(
    r"^\.env|secret|credential|private_key|password|passwd|api_key|apikey|"
    r"access_token|auth_token|\.(?:key|pem|p12|pfx)$",
    re.IGNORECASE,
)
EXCLUDED_DIRECTORIES = {
    ".git", ".remember", ".ruff_cache", ".pytest_cache", ".secrets", ".venv",
    ".worktrees", "__pycache__", "credentials", "node_modules", "private", "secrets",
    "tests", "tmp",
}
CENTRAL_ENTRIES = (
    "Dockerfile", ".dockerignore", "package.json", "package-lock.json",
    "provider-specs", "src", "ui", "scripts/export-contracts.ts", "python/pyproject.toml",
    "python/rental_bridge", "python/locks", "tsconfig.json", "tsconfig.server.json",
    "vite.config.ts",
)


def stage_build(source_root: Path, destination: Path, central_root: Path) -> dict:
    """Validate providers, then atomically replace the generated Docker context."""
    source_root, central_root = source_root.resolve(), central_root.resolve()
    destination = Path(os.path.abspath(destination))
    providers = _validate_providers(source_root)
    _validate_destination(destination, central_root)
    return _write_staging(providers, destination, central_root)


def _write_staging(providers: list[dict], destination: Path, central_root: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        _copy_central_project(central_root, temporary)
        manifest = _stage_providers(providers, temporary)
        content = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        _write_bytes(temporary / "build-manifest.json", content)
        _write_bytes(temporary / STAGING_MARKER, b"mcp-rentals-build-context-v1")
        _normalize_directory_permissions(temporary)
        _replace_staging(temporary, destination)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _validate_destination(destination: Path, central_root: Path) -> None:
    expected = central_root / ".staging"
    if destination != expected:
        raise ValueError(f"Staging destination must be {expected}")
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError(f"Staging destination must be a real directory: {destination}")
    marker = destination / STAGING_MARKER
    if destination.exists() and (not marker.is_file() or marker.read_bytes() != b"mcp-rentals-build-context-v1"):
        raise ValueError(f"Refusing to replace unmarked staging directory: {destination}")


def _replace_staging(temporary: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}-backup-{os.getpid()}")
    if backup.exists():
        raise ValueError(f"Refusing to replace existing staging backup: {backup}")
    if destination.exists():
        os.replace(destination, backup)
    try:
        os.replace(temporary, destination)
    except OSError:
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _validate_providers(source_root: Path) -> list[dict]:
    providers = []
    for provider_id, layouts in PROVIDER_LAYOUTS.items():
        provider_root = source_root / provider_id
        if not provider_root.is_dir():
            raise ValueError(f"Missing provider source: {provider_id}")
        files = _provider_files(provider_root, layouts)
        if not any(path.suffix == ".py" for path in files):
            raise ValueError(f"No Python source files found for provider: {provider_id}")
        providers.append({"id": provider_id, "root": provider_root,
                          "files": files, "revision": _local_revision(provider_root)})
    return providers


def _provider_files(provider_root: Path, layouts: tuple[str, ...]) -> list[Path]:
    files = [provider_root / name for name in ("pyproject.toml", "requirements.txt")
             if (provider_root / name).is_file()]
    for layout in layouts:
        directory = provider_root / layout
        if directory.is_dir():
            files.extend(_allowed_files(directory))
    return sorted(set(files), key=lambda path: path.relative_to(provider_root).as_posix())


def _allowed_files(directory: Path) -> list[Path]:
    files = []
    for path in directory.rglob("*"):
        relative_parts = path.relative_to(directory).parts
        if path.is_symlink() or not path.is_file():
            continue
        if any(part in EXCLUDED_DIRECTORIES for part in relative_parts):
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES or SENSITIVE_PATTERN.search(path.name):
            continue
        files.append(path)
    return files


def _local_revision(provider_root: Path) -> str:
    try:
        command = ["git", "-c", "safe.directory=*", "-C", str(provider_root), "rev-parse", "HEAD"]
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f"Cannot identify local Git revision for {provider_root.name}") from error
    return result.stdout.strip()


def _stage_providers(providers: list[dict], staging_root: Path) -> dict:
    items = [_stage_provider(provider, staging_root) for provider in providers]
    return {"version": 1, "providers": items}


def _stage_provider(provider: dict, staging_root: Path) -> dict:
    source_root = provider["root"]
    target_root = staging_root / "sources" / provider["id"]
    digest = hashlib.sha256()
    for source_file in provider["files"]:
        relative_path = source_file.relative_to(source_root)
        content = source_file.read_bytes()
        _write_bytes(target_root / relative_path, content)
        digest.update(relative_path.as_posix().encode("utf-8") + b"\0" + content + b"\0")
    return {
        "id": provider["id"], "git_revision": provider["revision"],
        "source_digest": digest.hexdigest(), "file_count": len(provider["files"]),
    }


def _copy_central_project(central_root: Path, staging_root: Path) -> None:
    for entry in CENTRAL_ENTRIES:
        source = central_root / entry
        if source.is_dir():
            for path in _allowed_files(source):
                _write_bytes(staging_root / path.relative_to(central_root), path.read_bytes())
            continue
        if source.is_file() and not SENSITIVE_PATTERN.search(source.name):
            _write_bytes(staging_root / source.relative_to(central_root), source.read_bytes())


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, 0o644)
    os.utime(path, (0, 0))


def _normalize_directory_permissions(root: Path) -> None:
    for directory in sorted((root, *root.rglob("*")), key=lambda item: len(item.parts), reverse=True):
        if directory.is_dir():
            os.chmod(directory, 0o755)
            os.utime(directory, (0, 0))


def main() -> int:
    central_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=central_root.parent)
    parser.add_argument("--destination", type=Path, default=central_root / ".staging")
    arguments = parser.parse_args()
    manifest = stage_build(arguments.source_root, arguments.destination, central_root)
    print(f"Staged {len(manifest['providers'])} providers at {arguments.destination.resolve()}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
