# Übergabe (Stand wird nach jedem Feature aktualisiert)

## Was ist das?
Manim Studio („Ganim“): eine PySide6-Desktop-App, mit der man Animationen für
Manim Community Edition per Maus baut. Die App erzeugt ein deterministisches
Manim-Skript (ohne `eval`/`exec` von Nutzereingaben) und rendert es mit Manim.

## Starten
```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m manim_studio
```
Zum Rendern werden zusätzlich gebraucht: FFmpeg (Manim bringt PyAV mit) und
für Formeln eine LaTeX-Installation (`latex`, `dvisvgm`).

## Testen
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q          # alles, ca. 5 min (über 400 Tests)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -m "not manim"   # ohne echte Renderläufe, ca. 1 min
.venv/bin/ruff check manim_studio tests tools examples packaging
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/fuzz_sessions.py --sessions 30 --seed 1   # Zufallssitzungen
```
Ruff ist in `pyproject.toml` auf `F` und `I` eingestellt. Kein `ruff format`,
das würde den ganzen Code umformatieren.
CI (GitHub Actions) führt Lint und alle Tests unter Python 3.10 (ohne LaTeX)
und 3.13 (mit LaTeX) aus.

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
- eingeschränktes 3D (Achsen, Flächen, Kurven, Körper inkl. platonischer Körper, 3D-Pfeile/-Punkte, Kamera)
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
- Neue Objektart „3D-Körper“ (Kugel, Würfel, Quader, Kegel, Zylinder, Torus):
  - Platziert in Koordinaten der 3D-Achsen, die bei Bedarf automatisch angelegt werden.
  - Skalieren und Farbe animierbar.
- Bühne: 3D-Flächen und -Körper werden jetzt korrekt gefüllt. Vorher löschten sich Vorder- und Rückseiten gegenseitig aus.
- Neuer Kurventyp „Implizite Kurve f(x, y) = 0“:
  - Manim: `plot_implicit_curve` bzw. `ImplicitFunction`.
  - Bühne: Marching Squares, gecacht.
  - Mit Parametern wird die Kurve per `always_redraw` mitgezogen.
- 5 neue Vorlagen: Satz des Pythagoras, Umlaufbahn mit Spur, Strömung (Vektorfeld), 3D-Körper mit Kamerafahrt, Kegelschnitte (implizit). Alle gerendert und geprüft.
- Verbundener Export (alle Szenen in einem Video) funktioniert jetzt auch mit 3D-Szenen. Basis ist dann `ThreeDScene`, 2D-Teile laufen in der Draufsicht.
- Neue Objektart „Aufzählung“:
  - Aus Text gebaut, braucht also kein LaTeX.
  - Zeichen wählbar: •, –, 1., a) oder keins.
- Neue Animation „Nacheinander zeigen“ für Listen und Gruppen (`LaggedStart`).
- „Drehen“ kann jetzt um einen festen Punkt drehen (`Rotate(..., about_point=...)`), z. B. für Uhrzeiger, Pendel oder den Einheitskreis.
- Menü „Zeitleiste“:
  - „Kamera auf Auswahl zoomen“ legt einen Schritt mit Kamerafahrt und Zoom auf die markierten Objekte an, bei Bedarf samt Kamera.
  - „Kamera zurück auf das ganze Bild“.
- Fuzzing Runde 4:
  - Duplizieren und Kopieren einer Gruppe übernahm die Mitglieder nicht und erzeugte leere Gruppen. Behoben.
  - Objekte, die nach Schrumpfen, Entstehen rückwärts, Wegschreiben oder Ersetzen später wieder verwendet werden, bleiben jetzt intakt: Der Ausgang läuft auf einer Kopie (`self.remove(obj)` + `Animation(obj.copy())`). Vorher gab es NaN-Abstürze bzw. falsche Formen; `save_state`/`restore` reichte nicht, weil `become()` bei Strukturwechsel versagt.
- Neue Objektart „Netzwerk (Graph)“:
  - Knoten und Kanten als Text eingeben, gerichtet oder ungerichtet, mit Text-Labels ohne LaTeX.
  - Layouts: Kreis, Federmodell, Kamada-Kawai, Schalen, Spirale, Baum.
  - Die Positionen berechnet die App (networkx) und gibt sie explizit an Manim weiter, daher sind Bühne und Video identisch.
- Einstellung „Vorschauqualität“: schnell (480p, 15 fps) oder flüssig (720p, 30 fps).

### Tagschicht 12.10. (Cloud-Session)
- Neue Animationen: „Knoten/Kanten hervorheben“ (Netzwerke), „Lineare Abbildung“ (`ApplyMatrix`).
- Kopplung (Updater): folgt einem Objekt / Position aus Formel mit Parametern; auch die 2D-Kamera kann folgen. Code: `model/attach.py`.
- Neue szenenbezogene Konfliktregel `model/conflicts.py`: Objekte, die Manim aus einem Parameter neu zeichnet, nicht im selben Schritt animieren, in dem sich der Parameter ändert (Absturz aus dem Fuzzing).
- Vorlagen: Präsentationsfolie, Graphentheorie, Lineare Abbildung (jetzt 13).
- Release-Vorbereitung: Version 0.9.0, MIT-LICENSE, README (englisch) mit echten Renderings, `docs/ANLEITUNG.md` (deutsch), CHANGELOG, CONTRIBUTING, CI, `examples/` (9 Projekte, erzeugt von `tools/make_examples.py`).
- Kompatibilität: Python 3.10–3.13, Manim 0.19–0.22. PySide6 6.12 stürzt unter Python < 3.12 ab → dort `<6.12`. PNG-Export nutzt `-s`.
- Experimentelle App-Bündel: `packaging/` + Workflow `bundle.yml` (nur manuell). Unter Linux geprüft, Windows/macOS ungetestet.
- Nachmittag: Wertetabelle, Polar-Gitter, Sekante (h → 0 wird zur Tangente) mit Vorlage (jetzt 14), platonische Körper, gebogener Pfeil (`model/curved.py`, rechnet Manims Geometrie exakt nach), 3D-Tiefensortierung auf der Bühne.
- Fixes: gestrichelte Linien der Länge 0 brachen Manim 0.19 ab (`studio_dashed_line`); Objektnamen wie `x0` oder `studio_plot` verdeckten Teile des Skripts (`naming.BUILD_LOCALS`, `HELPER_FUNCTIONS`).

### Halbfertig
- (nichts)

### Als Nächstes
- Freigabe durch den Nutzer: Tag/Release v0.9.0, ggf. PyPI (siehe WORK_LOG.md, offene Entscheidungen).
- Bundle-Workflow einmal von Hand starten und Windows/macOS prüfen.
- Ideen: Skript-Import erweitern (liest bisher nur einfache Szenen), komplexe Ebene (Beschriftung braucht LaTeX), nichtlineare Abbildungen (`ApplyComplexFunction`).
- Testlauf: Die volle Suite braucht ca. 5 Minuten (über 400 Tests, davon rund 45 echte Manim-Läufe).
