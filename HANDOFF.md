# Übergabe (Stand wird nach jedem Feature aktualisiert)

## Was ist das?
Manim Studio („Ganim“): eine PySide6-Desktop-App, mit der man Animationen für
Manim Community Edition per Maus baut. Die App erzeugt ein deterministisches
Manim-Skript (ohne `eval`/`exec` von Nutzereingaben) und rendert es mit Manim.

## Starten
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m manim_studio
```
Zum Rendern werden zusätzlich gebraucht: FFmpeg (Manim bringt PyAV mit) und
für Formeln eine LaTeX-Installation (`latex`, `dvisvgm`).

## Testen
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q          # alles, ca. 2–3 min
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -m "not manim"   # ohne echte Renderläufe
.venv/bin/ruff check --select F,I --line-length 200 manim_studio tests examples
```
Wichtig: ruff nur mit `--select F,I`. Ein normales `ruff --fix` formatiert
den ganzen Code um.

## Aufbau (Kurzfassung)
- `manim_studio/model/`: Datenmodell, Geometrie, Graphen und Analyse, Daten, 3D, Validierung, Serialisierung (`.msproj`)
- `manim_studio/codegen/`: Erzeugung des Manim-Skripts
- `manim_studio/render/`: Manim-Aufruf, Umgebungsprüfung
- `manim_studio/ui/`: Hauptfenster, Bühne, Panels, Dialoge, Theme
- `manim_studio/i18n/`: alle UI-Texte (Deutsch und Englisch, `de.py` und `en.py`)
- `manim_studio/plugins.py`: Erweiterungen (opt-in), Beispiel in `examples/plugins/`
- `tests/`: pytest; mit `-m manim` markierte Tests rendern wirklich

## Stand
Siehe Abschnitte unten. Entscheidungen und offene Fragen stehen in `WORK_LOG.md`.

### Funktioniert (getestet)
- Objekte, Bühne, Inspektor, Zeitleiste, Vorschau, Export MP4/GIF/PNG/.py
- Rückgängig/Wiederholen, mehrere Szenen, Umgebungsprüfung
- Graphen mit Analyse, Parameter-Animation, Daten und Diagramme, Flächen
- eingeschränktes 3D (Achsen, Flächen, Kurven, Kamera)
- Vorlagen, Stile, Bausteine, Projektpakete, Autosave, Skript-Import
- Erweiterungen, Manim-Installation per pip

### Änderungen der Nacht vom 12.10. (neueste unten)
- Export: Transparenz funktionierte mit Manim 0.22 nicht (MP4 hat keinen Alphakanal). Jetzt wird automatisch MOV erzeugt. Neue Formate: WebM und MOV, beide mit Transparenz.
- Robustheit (gefunden per Fuzzing: zufällige Bearbeitungen über den echten Controller plus Manim-Dry-Run der erzeugten Skripte):
  - Neue Regel „gleichzeitig spielbar“ (`types.simultaneous_conflicts`), gemeinsam für Validierung, Codegen und Controller. Konflikte landen beim Hinzufügen automatisch in einem neuen Schritt.
  - Abhängige Objekte (Tangente, Fläche, Datenpunkte, 3D-Fläche, Ableitung) bringen fehlende Achsen bzw. Graphen beim Einfügen mit und werden mit ihrem Host gelöscht.
  - Manim-Abstürze behoben: Pfeil nach Verwandlung in eine Gruppe (`studio_shape`), Pfad entlang gestrichelter Linie, Gruppe mit Parameter, Inspektor bei veralteter Auswahl.
  - Aufnahme lehnt unpassende Animationen ab (z. B. Bewegen eines Parameters).
- 6 neue Animationen:
  - Vom Rand wachsen (GrowFromEdge)
  - Tippen mit Cursor (TypeWithCursor, nur Text)
  - Wegschreiben (Unwrite)
  - Kopie verwandeln (TransformFromCopy)
  - Lichtlauf (ShowPassingFlash)
  - Ausbreiten (Broadcast)
  - Ein- und Ausblenden haben jetzt einen Zoom-Parameter.
  - Alle sechs sind in der Bühnen-Wiedergabe, der Hover-Vorschau, im Codegen und im Skript-Import enthalten und mit Manim getestet.
- Neue Objektart „Markierung“ (Rahmen, Hintergrund, Unterstreichen, Durchstreichen):
  - Hängt an einem Objekt und folgt ihm (`always_redraw`).
  - Ein Hintergrund liegt automatisch hinter seinem Ziel.
  - Wird mit dem Ziel gelöscht.
- Kleine Bildschirme: Anordnen-Buttons und Zeitleisten-Texte klappen ein, sodass das Fenster ab etwa 1280 px Breite vollständig nutzbar ist.
- `self.add(...)` im Skript folgt jetzt der Ebenenreihenfolge.
- 3D-Szenen: Kamerafahrten (Bewegen, Zoom, Rollen) funktionieren jetzt über einen unsichtbaren Steuerrahmen (`studio_camera_frame`). Vorher war nur Umkreisen erlaubt.
- 2D-Szenen: Kamera-Drehen wird verständlich abgelehnt, weil Manims 2D-Kamera das Bild nur verzerrt hätte.
- Verschachtelte Gruppen bleiben nach dem Löschen ihrer Mitglieder nicht mehr leer zurück.
- Neue Objektart „Winkel“ zwischen zwei Linien (Angle bzw. RightAngle):
  - Optional mit Symbol oder Gradzahl beschriftet.
  - Folgt den Linien (`always_redraw`), mit umgekehrten Linien und Außenwinkel.
  - Bühne und Manim stimmen überein.
- Neue Objektart „Spur“ (TracedPath):
  - Zeichnet den Weg eines Objekts auf, optional mit verblassendem Schweif.
  - Beginnt am Start oder dort, wo sie eingeblendet wird. Der Codegen macht daraus `self.add`, weil FadeIn auf TracedPath in Manim abstürzt.
  - Auf der Bühne wird die Spur aus der Zeitleiste abgetastet (`model/traces.py`, gecacht).
- Fuzzing Runde 3:
  - „Kopie verwandeln“ wird jetzt als `ReplacementTransform(quelle.copy(), ziel)` erzeugt (gleiches Bild, Ziel bleibt intakt).
  - Kopieren und Einfügen in eine andere Szene bringt fehlende Hosts (Achsen, Graph, Ziel) mit.
- Neue Objektart „Vektorfeld“:
  - Pfeile (ArrowVectorField) oder Stromlinien (StreamLines, optional fließend).
  - Farbskala nach Stärke, Parameter möglich (Pfeile mit `always_redraw`).
  - Die Bühne bildet Manim exakt nach (gleiches Gitter, gleicher Zufalls-Seed). Stromlinien sind gecacht.
- 3D-Flächen und 3D-Kurven mit Parametern werden jetzt mitanimiert. Vorher erkannte `parameter_users` nur Funktionsgraphen.
- Warnung bei Ausblenden oder Verwandeln von Objekten, die gerade unsichtbar sind (Manim ließe sie aufblitzen).

### Halbfertig
- (nichts)

### Als Nächstes
- Release-Politur (README, Lizenz, CI, PyInstaller-Builds) übernimmt die Cloud-Session.
