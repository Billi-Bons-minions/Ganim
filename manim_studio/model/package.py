"""Project packages: one ZIP file with the project and all images and sounds it uses."""

from __future__ import annotations

import copy
import zipfile
from pathlib import Path, PurePosixPath

from manim_studio.model.assets import resolve_asset_path
from manim_studio.model.entities import Project
from manim_studio.model.serialization import FILE_SUFFIX, ProjectFormatError, dumps_project, loads_project
from manim_studio.model.types import ObjectKind

PACKAGE_SUFFIX = ".mspkg"
PROJECT_ENTRY = "project" + FILE_SUFFIX
ASSET_FOLDER = "assets"
MAX_PACKAGE_SIZE = 2 * 1024**3


def _asset_references(project: Project) -> list[tuple[object, str, str]]:
    """``(holder, attribute or key, path)`` for every file the project uses."""
    references = []
    for scene in project.scenes:
        for obj in scene.objects:
            if obj.kind == ObjectKind.IMAGE and str(obj.params.get("path", "")).strip():
                references.append((obj.params, "path", str(obj.params["path"])))
        for step in scene.steps:
            if step.sound.strip():
                references.append((step, "sound", step.sound))
    return references


def _unique_name(name: str, used: set[str]) -> str:
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate, number = name, 2
    while candidate.lower() in used:
        candidate = f"{stem}_{number}{suffix}"
        number += 1
    used.add(candidate.lower())
    return candidate


def save_package(project: Project, target: str | Path, base_dir: str | Path | None) -> list[str]:
    """Write the package; returns the paths of files that could not be found."""
    packed = copy.deepcopy(project)
    missing: list[str] = []
    files: dict[Path, str] = {}
    used: set[str] = set()
    for holder, key, raw in _asset_references(packed):
        source = resolve_asset_path(raw, base_dir)
        if not source.is_file():
            missing.append(raw)
            continue
        entry = files.get(source)
        if entry is None:
            entry = f"{ASSET_FOLDER}/{_unique_name(source.name, used)}"
            files[source] = entry
        if isinstance(holder, dict):
            holder[key] = entry
        else:
            setattr(holder, key, entry)
    target = Path(target)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(PROJECT_ENTRY, dumps_project(packed))
        for source, entry in files.items():
            archive.write(source, entry)
    return missing


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def extract_package(package: str | Path, folder: str | Path) -> Path:
    """Unpack a package into ``folder`` and return the project file inside it."""
    folder = Path(folder)
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if PROJECT_ENTRY not in names:
            raise ProjectFormatError("not a Manim Studio package")
        if sum(info.file_size for info in archive.infolist()) > MAX_PACKAGE_SIZE:
            raise ProjectFormatError("package is too large")
        for name in names:
            if not _safe_member(name):
                raise ProjectFormatError(f"unsafe file name in package: {name}")
        loads_project(archive.read(PROJECT_ENTRY).decode("utf-8"))
        folder.mkdir(parents=True, exist_ok=True)
        archive.extractall(folder)
    return folder / PROJECT_ENTRY
