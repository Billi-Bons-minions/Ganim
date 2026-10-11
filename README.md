# Manim Studio

Mit Manim Studio erstellst du Animationen für die [Manim Community Edition](https://www.manim.community) per Maus, ohne eine Zeile Code zu schreiben.
Im Hintergrund erzeugt die App ein gültiges Manim-Skript und rendert es mit Manim. Das Skript lässt sich jederzeit ansehen und exportieren.

Die Oberfläche ist auf **Deutsch und Englisch** verfügbar (umschaltbar unter *Bearbeiten → Einstellungen*).

---

## Funktionen

| Bereich | Möglichkeiten |
|---|---|
| **Objekte** | Kreis, Quadrat, Rechteck, Dreieck, Ellipse, Linie, Pfeil, Punkt, Text, Formel (MathTex), Koordinatensystem (Axes), Zahlenebene (NumberPlane), Funktionsgraph (Term als Eingabe, z. B. `2x^2 + sin(x)`), Bild (PNG/JPG/SVG) |
| **Bühne** | Manim-Koordinaten (Ursprung in der Mitte, y nach oben, Rahmen 14,22 × 8), Raster, Einrasten, Auswählen (auch per Rahmen), Verschieben, Skalieren und Drehen mit Griffen, Zoom (Strg + Mausrad), Verschieben der Ansicht mit der mittleren Maustaste |
| **Eigenschaften** | Name, Position, Größe, Drehung, Linien- und Füllfarbe (Manim-Palette oder frei), Deckkraft, Strichstärke, Text, Schriftgröße, Ebene, Sichtbarkeit am Anfang |
| **Zeitleiste** | Schritte mit einer oder mehreren gleichzeitigen Animationen (= ein `self.play(...)`), Warte-Schritte (= `self.wait(...)`), Hinzufügen, Löschen, Duplizieren, Umsortieren per Drag & Drop. Ein Klick auf einen Schritt zeigt den Zustand nach diesem Schritt |
| **Animationen** | Create, Write, DrawBorderThenFill, FadeIn, FadeOut, GrowFromCenter, Transform, ReplacementTransform, Bewegen, Skalieren, Drehen, Farbe ändern, Indicate, Circumscribe, Uncreate, jeweils mit Dauer und Rate-Funktion |
| **Vorschau & Export** | Schnellvorschau (480p) im eingebetteten Player; Export als MP4, GIF oder PNG (Ende der Szene oder Zustand nach einem Schritt), Auflösung, FPS, Qualität, Hintergrundfarbe, Ausgabeordner, Fortschritt und Abbrechen |
| **Code** | Schreibgeschützte Code-Ansicht mit Syntaxhervorhebung, Export als `.py` |
| **Projekt** | Neu/Öffnen/Speichern/Speichern unter (JSON, `.msproj`), zuletzt geöffnete Projekte, mehrere Szenen pro Projekt, Undo/Redo für alle Änderungen, Kopieren/Einfügen/Duplizieren/Löschen |
| **Robustheit** | Prüfung von Manim, FFmpeg und LaTeX beim Start; verständliche Fehlermeldungen und vollständiges Render-Log; Nutzereingaben werden sicher eingebettet (kein `eval`) |

---

## Installation

Voraussetzung ist **Python 3.10 oder neuer**. Manim braucht außerdem einige Systembibliotheken.
**LaTeX ist optional**: Ohne LaTeX funktioniert alles außer Formeln (MathTex).

> FFmpeg: Manim ab Version 0.18 bringt über das Paket *PyAV* eigene FFmpeg-Bibliotheken mit. Ein separat installiertes FFmpeg ist deshalb meist nicht nötig, schadet aber nicht.

### Windows

1. Python von [python.org](https://www.python.org/downloads/) installieren und dabei *„Add Python to PATH“* ankreuzen.
2. Optional für Formeln: [MiKTeX](https://miktex.org/download) installieren und die automatische Paketinstallation erlauben.
3. In der Eingabeaufforderung (im Projektordner):
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

### macOS

1. [Homebrew](https://brew.sh) installieren, dann:
   ```bash
   brew install python py3cairo pango pkg-config ffmpeg
   ```
2. Optional für Formeln:
   ```bash
   brew install --cask mactex-no-gui
   ```
3. Im Projektordner:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

### Linux (Debian/Ubuntu)

1. Systempakete installieren:
   ```bash
   sudo apt install python3-venv python3-dev build-essential libcairo2-dev libpango1.0-dev pkg-config ffmpeg
   ```
2. Optional für Formeln:
   ```bash
   sudo apt install texlive texlive-latex-extra dvisvgm
   ```
3. Im Projektordner:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

Bei anderen Distributionen heißen die Pakete ähnlich (z. B. Fedora: `cairo-devel pango-devel`). Details stehen in der [Manim-Installationsanleitung](https://docs.manim.community/en/stable/installation.html).

---

## Starten

Bei aktivierter virtueller Umgebung im Projektordner:

```bash
python -m manim_studio
```

Ein Projekt lässt sich direkt mit öffnen: `python -m manim_studio meinprojekt.msproj`

Beim ersten Start prüft Manim Studio im Hintergrund, ob Manim, FFmpeg und LaTeX vorhanden sind. Fehlt etwas, erscheint ein Hinweis mit Installationsanleitung (erneut aufrufbar unter *Rendern → Systemprüfung*).
Liegt Manim in einer anderen Python-Umgebung, stellst du den Interpreter unter *Bearbeiten → Einstellungen → Python für Manim* ein.

---

## Bedienung in 2 Minuten

**Beispiel:** Ein Kreis erscheint, verwandelt sich in ein Quadrat, dann wird ein Text geschrieben.

1. Links in **Objekte hinzufügen** auf *Kreis*, *Quadrat* und *Text* klicken (oder sie auf die Bühne ziehen). Objekte mit der Maus platzieren; das Quadrat darf auf dem Kreis liegen.
2. Den **Kreis** anklicken, dann in der Zeitleiste **Animation ▾ → Erstellen (Create)**. Es entsteht *Schritt 1*.
3. **Kreis** anklicken, mit **Strg** zusätzlich das **Quadrat** anklicken, dann **Animation ▾ → Verwandeln (Transform)**. Das erste gewählte Objekt verwandelt sich in das zweite (*Schritt 2*).
4. Den **Text** anklicken, dann **Animation ▾ → Schreiben (Write)** (*Schritt 3*). Den Text änderst du rechts im Eigenschaften-Panel.
5. **F5** drücken: Die Vorschau wird gerendert und im Player abgespielt.
6. **Datei → Exportieren …**: Format *Video (MP4)*, Qualität und Ordner wählen, dann *Exportieren*.

### Wichtige Konzepte

- **Schritte:** Alle Animationen eines Schritts laufen gleichzeitig. *Animation ▾* legt einen neuen Schritt an; mit **+** neben der Animationsliste kommt eine Animation in den aktuellen Schritt.
- **Sichtbarkeit:** Ein Objekt ist automatisch unsichtbar, bis es durch eine Einblend-Animation (Create, Write, FadeIn …) erscheint oder als Ziel einer Verwandlung dient. Unsichtbare Objekte zeigt die Bühne als blasse „Geister“. Unter *Am Anfang sichtbar* lässt sich das fest einstellen.
- **Bühne und Zeitleiste:** Ist **Start** gewählt, ändert Ziehen, Skalieren und Drehen die Startwerte. Ist ein **Schritt** gewählt, verändert Ziehen den Zielwert der *Bewegen*-, *Skalieren*- oder *Drehen*-Animation dieses Objekts in genau diesem Schritt. Ohne passende Animation ist das Objekt dort gesperrt; ein Hinweis erklärt, warum.
- **Funktionsgraph:** Gibt es ein Koordinatensystem, wird ein neuer Graph automatisch daran gebunden (`axes.plot(...)`). Erlaubt sind `x`, Zahlen (auch `0,5`), `+ - * / ^`, Klammern, implizite Multiplikation (`2x`, `3sin(x)`), `pi`, `e`, `tau` und die Funktionen `sin cos tan asin acos atan sinh cosh tanh exp log ln log10 log2 sqrt abs floor ceil sign`.

### Tastenkürzel

| Aktion | Kürzel |
|---|---|
| Neu / Öffnen / Speichern / Speichern unter | Strg+N / Strg+O / Strg+S / Strg+Umschalt+S |
| Rückgängig / Wiederholen | Strg+Z / Strg+Y bzw. Strg+Umschalt+Z |
| Ausschneiden / Kopieren / Einfügen / Duplizieren | Strg+X / Strg+C / Strg+V / Strg+D |
| Löschen (Objekte bzw. Schritt, je nach Fokus) | Entf |
| Alles auswählen | Strg+A |
| Objekt verschieben | Pfeiltasten (mit Umschalt: 1 Einheit) |
| Einrasten kurz aussetzen | Alt beim Ziehen |
| Eine Ebene nach vorne / hinten | Strg+] / Strg+[ |
| Schritt hinzufügen / Warte-Schritt | Strg+T / Strg+W |
| Vorheriger / nächster Schritt, Start, Ende | Bild↑ / Bild↓ / Pos1 / Ende |
| Raster / Einrasten / Unsichtbare zeigen | Strg+G / Strg+Umschalt+G / Strg+H |
| Einpassen / Zoom | Strg+0 / Strg+Plus, Strg+Minus, Strg+Mausrad |
| Vorschau / Abbrechen / Exportieren / Skript exportieren | F5 / Umschalt+F5 / Strg+E / Strg+Umschalt+E |
| Neue Szene / Szene umbenennen | Strg+Umschalt+N / F2 |

---

## Das erzeugte Skript

Die Code-Ansicht zeigt jederzeit das vollständige Skript. Über *Datei → Skript exportieren* speicherst du es als `.py`-Datei und kannst es ohne Manim Studio rendern:

```bash
manim -pql meine_szene.py Szene1
```

Jede Szene wird zu einer Klasse (Name aus dem Szenennamen, z. B. *Szene 1* → `Szene1`), jedes Objekt zu einer Variablen (z. B. *Kreis 1* → `kreis_1`), jeder Schritt zu genau einem `self.play(...)` oder `self.wait(...)`.
Bewegen, Skalieren, Drehen und Farbe ändern desselben Objekts im selben Schritt werden zu einer `.animate`-Kette zusammengefasst.

Texte, Formeln und Dateipfade werden als geprüfte String-Literale eingebettet; Funktionsterme werden geparst und gegen eine feste Liste erlaubter Bausteine geprüft. Es wird nie `eval` auf Eingaben angewendet.

---

## Projektstruktur

```
manim_studio/
├── __main__.py          Einstieg für "python -m manim_studio"
├── app.py               QApplication, Sprache, Hauptfenster
├── i18n/                alle Texte zentral: de.py, en.py, tr()
├── model/               Datenmodell (einzige Quelle der Wahrheit), ohne Qt
│   ├── entities.py      Dataclasses: Project → Scene → SceneObject / Step → Animation
│   ├── types.py         Enums, Rate-Funktionen, Farbpalette
│   ├── schema.py        Parameter je Objekt-/Animationstyp (steuert das Eigenschaften-Panel)
│   ├── expression.py    sicherer Parser für Funktionsterme
│   ├── geometry.py      Achsen-Layout, Abtastung von Graphen
│   ├── state.py         Zustand der Szene nach Schritt n
│   ├── operations.py    alle Änderungen am Modell
│   ├── stage_edits.py   Regeln für kontextabhängiges Bearbeiten auf der Bühne
│   ├── animation_builder.py, factory.py, validation.py, serialization.py, assets.py
├── codegen/             Modell → Manim-Skript (deterministisch), ohne Qt
├── render/              Manim per QProcess, Fortschritt, Fehleranalyse, Systemprüfung, LaTeX-Vorschau
└── ui/                  Fenster, Bühne, Panels, Dialoge (keine Manim-Logik)
    ├── document.py      Projekt + QUndoStack (Snapshot-Befehle)
    ├── controller.py    alle Bearbeitungsbefehle
    ├── stage/           QGraphicsView-Bühne, Zeichnen der Objekte, Griffe
    ├── panels/          Bibliothek, Objektliste, Eigenschaften, Zeitleiste, Player, Code, Log
    └── dialogs/         Export, Einstellungen, Systemprüfung, Meldungen
tests/                   pytest
```

Die UI ändert nur das Modell (über `ProjectDocument.edit_scene`, damit jede Änderung rückgängig gemacht werden kann). Bühne, Code-Ansicht und Zeitleiste werden aus dem Modell neu aufgebaut.

---

## Tests

```bash
pytest                 # alle Tests (inkl. echter Manim-Renderläufe, ca. 10–30 s)
pytest -m "not manim"  # nur die schnellen Tests ohne Manim-Rendering
```

Die Tests prüfen unter anderem:
- den Code-Generator gegen erwartete Skripte (vollständige Golden-Tests und alle Objekt- und Animationstypen),
- die sichere Einbettung bösartiger Eingaben,
- den Formel-Parser, Zustandsberechnung, Speichern/Laden (identisches Modell nach dem Neuladen),
- die Vollständigkeit beider Sprachen,
- das echte Rendern erzeugter Skripte mit Manim,
- einen Offscreen-Durchlauf der Oberfläche.

---

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| „Manim ist im eingestellten Python-Interpreter nicht installiert“ | `pip install manim` in der verwendeten Umgebung ausführen oder unter *Einstellungen → Python für Manim* den richtigen Interpreter wählen. |
| Formeln werden nur als grauer Quelltext angezeigt | LaTeX fehlt (`latex` und `dvisvgm` müssen im PATH liegen) oder die Formel enthält einen Fehler; der Hinweis im Eigenschaften-Panel nennt den Grund. |
| Rendern schlägt fehl | Die Meldung nennt die Ursache; das vollständige Log steht im Tab *Render-Log* und lässt sich speichern. |
| Die Vorschau spielt nicht ab | Mit *Extern öffnen* im Systemplayer abspielen. Die Datei liegt im Cache-Ordner der App. |
| Unter Linux startet die App nicht (Qt-Plattform-Fehler) | Fehlende Qt-Abhängigkeiten installieren, z. B. `sudo apt install libxcb-cursor0`. |
