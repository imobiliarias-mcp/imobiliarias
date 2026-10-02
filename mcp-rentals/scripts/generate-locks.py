"""Generate hash-locked Python 3.14 provider environments with pip-tools."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROVIDER_IDS = (
    "alecorretoramg", "arthusoimoveis", "cabralporto", "casalinhares", "epifanioimoveis",
    "helenaimoveis", "imobiliariaportalmg", "imobiliariavaleinvest", "imovelweb",
    "marcioimoveis", "minascaixaimoveis", "niltoncorretordeimoveis", "novaimobiliaria",
    "veraimobiliaria", "vivareal",
)
DEV_PACKAGE_NAMES = {"build", "coverage", "mypy", "pytest", "ruff", "tox"}
PROVIDER_EXTRAS = {
    "imovelweb": ("lxml>=5.0.0", "patchright>=1.63.0"),
    "minascaixaimoveis": ("requests>=2.32.0",),
}


def collect_provider_dependencies(provider_id: str, source_root: Path, bridge_dependencies: list[str]) -> list[str]:
    """Combine bridge and source runtime requirements without provider dev tools."""
    dependencies = list(bridge_dependencies)
    provider_root = source_root / provider_id
    project_file = provider_root / "pyproject.toml"
    requirements_file = provider_root / "requirements.txt"
    dependencies.extend(_source_dependencies(provider_id, project_file, requirements_file))
    dependencies.extend(PROVIDER_EXTRAS.get(provider_id, ()))
    return sorted({_runtime_requirement(value) for value in dependencies})


def _source_dependencies(
    provider_id: str, project_file: Path, requirements_file: Path
) -> list[str]:
    if project_file.is_file():
        return _project_dependencies(project_file)
    if requirements_file.is_file():
        return _requirements_dependencies(requirements_file)
    return list(_fallback_dependencies(provider_id))


def _project_dependencies(project_file: Path) -> list[str]:
    import tomllib
    with project_file.open("rb") as stream:
        project = tomllib.load(stream).get("project", {})
    return [str(value) for value in project.get("dependencies", [])]


def _requirements_dependencies(requirements_file: Path) -> list[str]:
    dependencies = []
    for line in requirements_file.read_text(encoding="utf-8").splitlines():
        requirement = line.split("#", 1)[0].strip()
        if not requirement or requirement.startswith(("-", ".")):
            continue
        if _package_name(requirement) in DEV_PACKAGE_NAMES:
            continue
        dependencies.append(requirement)
    return dependencies


def _fallback_dependencies(provider_id: str) -> tuple[str, ...]:
    if provider_id == "casalinhares":
        return ("httpx>=0.27.0",)
    raise ValueError(f"No project dependency metadata found for {provider_id}")


def _runtime_requirement(value: str) -> str:
    if _package_name(value) in DEV_PACKAGE_NAMES:
        raise ValueError(f"Development dependency is not allowed in a provider lock: {value}")
    return value.strip()


def _package_name(requirement: str) -> str:
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)", requirement.strip())
    if match is None:
        raise ValueError(f"Invalid Python requirement: {requirement}")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def _bridge_project(central_root: Path) -> dict:
    import tomllib

    project_file = central_root / "python" / "pyproject.toml"
    with project_file.open("rb") as stream:
        return tomllib.load(stream).get("project", {})


def generate_lock(
    dependencies: list[str], lock_path: Path, pip_compile: str, project_root: Path
) -> None:
    """Resolve exact platform wheels and hashes using the pinned pip-tools tool."""
    input_path = lock_path.with_name(f".{lock_path.stem}.requirements.in")
    input_path.write_text("\n".join(dependencies) + "\n", encoding="utf-8")
    try:
        _compile_lock(input_path, lock_path, pip_compile, project_root)
    finally:
        input_path.unlink(missing_ok=True)


def _compile_lock(input_path: Path, lock_path: Path, pip_compile: str, project_root: Path) -> None:
    command = [
        pip_compile, "--generate-hashes", "--resolver=backtracking", "--allow-unsafe",
        "--strip-extras", "--no-header", "--no-annotate", "--no-emit-index-url",
        "--output-file", lock_path.relative_to(project_root).as_posix(),
        input_path.relative_to(project_root).as_posix(),
    ]
    subprocess.run(command, check=True, cwd=project_root)


def generate_locks(central_root: Path, source_root: Path, selected: tuple[str, ...] | None) -> None:
    """Write selected locks without modifying provider source or environments."""
    bridge_project = _bridge_project(central_root)
    bridge_dependencies = bridge_project.get("dependencies", [])
    lock_directory = central_root / "python" / "locks"
    lock_directory.mkdir(parents=True, exist_ok=True)
    selected_providers = _providers_to_lock(selected)
    _generate_provider_locks(selected_providers, source_root, bridge_dependencies, lock_directory, central_root)
    _generate_dev_lock(bridge_project, lock_directory, central_root)


def _providers_to_lock(selected: tuple[str, ...] | None) -> tuple[str, ...]:
    if selected is not None:
        return selected
    return PROVIDER_IDS


def _generate_provider_locks(
    providers: tuple[str, ...], source_root: Path, dependencies: list[str],
    lock_directory: Path, project_root: Path,
) -> None:
    for provider_id in providers:
        provider_dependencies = collect_provider_dependencies(provider_id, source_root, dependencies)
        lock_path = lock_directory / f"{provider_id}.requirements.txt"
        generate_lock(provider_dependencies, lock_path, "pip-compile", project_root)


def _generate_dev_lock(bridge_project: dict, lock_directory: Path, project_root: Path) -> None:
    dependencies = list(bridge_project.get("dependencies", []))
    dependencies.extend(bridge_project.get("optional-dependencies", {}).get("dev", []))
    lock_path = lock_directory / "dev-requirements.txt"
    generate_lock(sorted(set(dependencies)), lock_path, "pip-compile", project_root)


def main() -> int:
    central_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=central_root.parent)
    parser.add_argument("--provider", choices=PROVIDER_IDS, action="append")
    arguments = parser.parse_args()
    selected_providers = None
    if arguments.provider:
        selected_providers = tuple(arguments.provider)
    try:
        generate_locks(central_root, arguments.source_root, selected_providers)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Lock generation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
