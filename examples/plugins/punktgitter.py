"""Beispiel: Punktgitter, Neon-Stil und eine Szenenvorlage.

Dient als Vorlage für eigene Erweiterungen.

Kopiere diese Datei in den Erweiterungsordner (Erweiterungen → Erweiterungen
verwalten … → Ordner öffnen) und aktiviere sie dort.
"""

from manim_studio.model.factory import create_animation, create_object, create_play_step, create_scene
from manim_studio.model.types import AnimationKind, ObjectKind


def add_dot_grid(context):
    """Fügt ein 5 × 3 Punktgitter ein."""
    for row in range(3):
        for column in range(5):
            context.add_object(ObjectKind.DOT, -4.0 + 2.0 * column, 2.0 - 2.0 * row, radius=0.12)
    context.message("Punktgitter eingefügt")


def greeting_scene():
    """Eine kleine Szene: Kreis erscheint, Text wird geschrieben."""
    scene = create_scene("Begrüßung")
    circle = create_object(ObjectKind.CIRCLE, "Kreis", -3.0, 0.0, radius=1.2)
    text = create_object(ObjectKind.TEXT, "Gruß", 2.0, 0.0, text="Hallo!")
    scene.objects += [circle, text]
    scene.steps.append(create_play_step([create_animation(AnimationKind.CREATE, circle.id)]))
    scene.steps.append(create_play_step([create_animation(AnimationKind.WRITE, text.id)]))
    return scene


def register(api):
    api.add_action("Punktgitter einfügen", add_dot_grid)
    api.add_style("Neon", {"stroke_color": "#39FF14", "fill_color": "#39FF14", "fill_opacity": 0.2, "stroke_width": 6.0})
    api.add_template("Begrüßung (Beispiel-Erweiterung)", greeting_scene)
