"""Packages, autosave and recovery."""

from __future__ import annotations

import zipfile

import pytest

from manim_studio.model.entities import Scene
from manim_studio.model.package import PROJECT_ENTRY, extract_package, save_package
from manim_studio.model.serialization import ProjectFormatError, load_project
from manim_studio.model.types import AnimationKind, ObjectKind
from tests.helpers import make_animation, make_object, make_project, play


def project_with_assets(tmp_path):
    (tmp_path / "bilder").mkdir()
    (tmp_path / "bilder" / "logo.png").write_bytes(b"png-data")
    (tmp_path / "ton.wav").write_bytes(b"wav-data")
    image = make_object(ObjectKind.IMAGE, "Logo", "i", path="bilder/logo.png")
    other = make_object(ObjectKind.IMAGE, "Fehlt", "j", path="weg.png")
    step = play(make_animation(AnimationKind.FADE_IN, "i"))
    step.sound = "ton.wav"
    return make_project(Scene(id="s", name="S", objects=[image, other], steps=[step]))


def test_package_round_trip(tmp_path) -> None:
    project = project_with_assets(tmp_path)
    package = tmp_path / "paket.mspkg"
    missing = save_package(project, package, tmp_path)
    assert missing == ["weg.png"]
    folder = tmp_path / "entpackt"
    project_file = extract_package(package, folder)
    restored = load_project(project_file)
    image = restored.scenes[0].objects[0]
    assert image.params["path"] == "assets/logo.png"
    assert (folder / "assets" / "logo.png").read_bytes() == b"png-data"
    assert (folder / restored.scenes[0].steps[0].sound).read_bytes() == b"wav-data"
    assert project.scenes[0].objects[0].params["path"] == "bilder/logo.png"


def test_unsafe_packages_are_rejected(tmp_path) -> None:
    bad = tmp_path / "bad.mspkg"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr(PROJECT_ENTRY, "{}")
    with pytest.raises(ProjectFormatError):
        extract_package(bad, tmp_path / "x")
    evil = tmp_path / "evil.mspkg"
    good_project = tmp_path / "ok.mspkg"
    save_package(project_with_assets(tmp_path), good_project, tmp_path)
    with zipfile.ZipFile(good_project) as source, zipfile.ZipFile(evil, "w") as archive:
        archive.writestr(PROJECT_ENTRY, source.read(PROJECT_ENTRY))
        archive.writestr("../../ausbruch.txt", "x")
    with pytest.raises(ProjectFormatError):
        extract_package(evil, tmp_path / "y")
    assert not (tmp_path / "ausbruch.txt").exists()


def test_autosave_and_recovery(tmp_path, qapp) -> None:
    from manim_studio.ui.autosave import AutoSaver
    from manim_studio.ui.document import ProjectDocument

    document = ProjectDocument("Szene 1")
    saver = AutoSaver(document, tmp_path / "autosave")
    assert not saver.save_now()
    document.edit_scene("x", document.project.scenes[0].id, lambda s: setattr(s, "background_color", "#112233"))
    assert saver.save_now()
    assert len(list((tmp_path / "autosave").glob("*.msproj"))) == 1

    later = ProjectDocument("Szene 1")
    second = AutoSaver(later, tmp_path / "autosave")
    backups = second.backups()
    assert len(backups) == 1 and saver.backups() == []
    assert second.restore(backups[0])
    assert later.project.scenes[0].background_color == "#112233" and later.is_dirty
    later.save(tmp_path / "gerettet.msproj")
    assert not later.is_dirty
    assert list((tmp_path / "autosave").glob("*.msproj")) == []
