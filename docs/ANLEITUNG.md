# Manim Studio – Anleitung (Deutsch)

Mit Manim Studio baust du Animationen für die [Manim Community Edition](https://www.manim.community) per Maus, ohne Code zu schreiben. Im Hintergrund erzeugt die App ein gültiges Manim-Skript und rendert es mit Manim. Das Skript kannst du jederzeit ansehen und exportieren.

Die Oberfläche ist auf Deutsch und Englisch verfügbar. Auf deutschen Systemen startet sie auf Deutsch; umstellen kannst du das unter *Bearbeiten → Einstellungen … → Sprache*.

![Manim Studio](images/screenshot-light.png)

## Installation

Du brauchst **Python 3.10 bis 3.13**. Manim braucht außerdem einige Systembibliotheken. **LaTeX ist optional**: Ohne LaTeX funktioniert alles außer Formeln (und Zahlen mit Einheit).

> FFmpeg: Manim bringt über das Paket *PyAV* eigene FFmpeg-Bibliotheken mit. Ein separat installiertes FFmpeg ist meist nicht nötig.

### Windows
1. Python von [python.org](https://www.python.org/downloads/) installieren und dabei *„Add Python to PATH“* ankreuzen.
2. Optional für Formeln: [MiKTeX](https://miktex.org/download) installieren und die automatische Paketinstallation erlauben.
3. In der Eingabeaufforderung:
   ```bat
   python -m venv manim-studio-env
   manim-studio-env\Scripts\activate
   pip install git+https://github.com/Billi-Bons-minions/Ganim
   manim-studio
   ```

### macOS
1. [Homebrew](https://brew.sh) installieren, dann `brew install python py3cairo pango pkg-config`
2. Optional für Formeln: `brew install --cask mactex-no-gui`
3. Dann:
   ```bash
   python3 -m venv manim-studio-env
   source manim-studio-env/bin/activate
   pip install git+https://github.com/Billi-Bons-minions/Ganim
   manim-studio
   ```

### Linux (Debian/Ubuntu)
1. `sudo apt install python3-venv python3-dev build-essential libcairo2-dev libpango1.0-dev pkg-config ffmpeg`
2. Optional für Formeln: `sudo apt install texlive texlive-latex-extra dvisvgm`
3. Dann:
   ```bash
   python3 -m venv manim-studio-env
   source manim-studio-env/bin/activate
   pip install git+https://github.com/Billi-Bons-minions/Ganim
   manim-studio
   ```

Beim nächsten Mal genügt es, die Umgebung zu aktivieren und `manim-studio` zu starten. Ein Projekt öffnest du direkt mit `manim-studio meinprojekt.msproj`.

Beim Start prüft Manim Studio im Hintergrund, ob Manim, FFmpeg und LaTeX vorhanden sind, und sagt dir, was fehlt (erneut unter *Rendern → Systemprüfung …*). Liegt Manim in einer anderen Python-Umgebung, stellst du den Interpreter unter *Bearbeiten → Einstellungen … → Python für Manim* ein.

## Die erste Animation in 2 Minuten

**Ziel:** Ein Kreis erscheint, verwandelt sich in ein Quadrat, dann wird ein Text geschrieben.

1. Links unter **Objekte** auf *Kreis*, *Quadrat* und *Text* klicken (oder auf die Bühne ziehen). Das Quadrat auf den Kreis legen.
2. Den **Kreis** anklicken, dann in der Zeitleiste **Animation ▾ → Erstellen (Create)**. Es entsteht *Schritt 1*.
3. Den **Kreis** anklicken, mit **Strg** zusätzlich das **Quadrat** anklicken, dann **Animation ▾ → Verwandeln (Transform)**. Das zuerst gewählte Objekt verwandelt sich in das zweite (*Schritt 2*).
4. Den **Text** anklicken, dann **Animation ▾ → Schreiben (Write)** (*Schritt 3*). Den Text änderst du rechts im Eigenschaften-Panel.
5. **Leertaste** spielt alles auf der Bühne ab, **F5** rendert eine echte Manim-Vorschau.
6. **Datei → Exportieren …**: Format *Video (MP4)*, Qualität und Ordner wählen, dann *Exportieren*.

Im Raum gibt es 3D-Achsen, eine Kamera, die du schwenken oder mit *Kamera dreht dauerhaft* gleichmäßig weiterdrehen lassen kannst (auch über Pausen hinweg, 0 °/s hält sie an), Flächen (z = f(x, y) oder als Parameterfläche x(u, v), y(u, v), z(u, v), z. B. Kugel oder Torus), Kurven, Körper (auch die platonischen Körper Tetraeder, Oktaeder, Ikosaeder und Dodekaeder), die sich mit *Im Raum bewegen* und *Im Raum drehen* animieren lassen sowie Pfeile, Strecken und Punkte (Bereich *3D* der Objektbibliothek oder Menü *Einfügen*).

Es geht auch ohne leere Bühne: Im Willkommensdialog gibt es fünf Beispielprojekte, und unter *Szene → Neue Szene aus Vorlage* findest du 20 Vorlagen (z. B. Kurvendiskussion, Wertetabelle und Graph, von der Sekante zur Tangente, Tangente wandert am Graphen, Integralfunktion F′ = f, Satz des Pythagoras, Graphentheorie, lineare Abbildung, komplexe Abbildung w = z², Lupe: lokal linear, Mengen im Venn-Diagramm).

## Wichtige Begriffe

- **Schritte:** Alle Animationen eines Schritts laufen gleichzeitig. Unter *Ablauf* lassen sie sich auch versetzt oder nacheinander abspielen. *Animation ▾* legt einen neuen Schritt an.
- **Sichtbarkeit:** Ein Objekt ist unsichtbar, bis eine Einblend-Animation (Erstellen, Schreiben, Einblenden …) es zeigt. Unsichtbare Objekte zeigt die Bühne als blasse „Geister“.
- **Bühne und Zeitleiste:** Ist **Start** gewählt, ändert Ziehen die Startposition. Ist ein **Schritt** gewählt, wird Ziehen, Skalieren und Drehen als Animation in diesem Schritt aufgenommen.
- **Parameter:** Ein Parameter (z. B. `a`) ist ein Regler. Du kannst ihn in allen Formeln verwenden (Graphen, Flächen, Tangenten, Flächen im Raum, Vektorfelder, Positionen) und mit *Wert ändern* animieren. Bei einer *Formel* rechnet die Option *Ergebnis ausrechnen* den Inhalt aus und hängt „= …“ an, auch mit Parametern (z. B. `\frac{a^2}{2} + 3 = 3.50`). Eine *Zahl* kann einen Parameter oder eine Formel aus Parametern anzeigen (Feld *Formel*, z. B. `a^2/2`); sie rechnet beim Animieren mit. In diesen Formeln (auch in Positionsformeln und beim Ergebnis einer Formel) kannst du Funktionswerte von Graphen verwenden: Heißt ein Graph `f`, schreibst du `f(a)` oder `f(2) + 1`. Das geht für Graphen y = f(x) mit einem Term und für Ableitungen (Graph dazu passend benennen, z. B. `g`).
- **Werkzeuge am Graphen:** Wähle einen Funktionsgraphen; im Eigenschaften-Panel fügen Knöpfe unter anderem Ableitung, Integralfunktion (F(x) = ∫ f(t) dt, numerisch berechnet), Nullstellen, Extrema, Tangente, Sekante, Punkt, Fläche, Riemann-Summe, Beschriftung oder Wertetabelle hinzu. Koppelst du die Schrittweite *h* einer Sekante an einen Parameter und lässt ihn gegen 0 laufen, wird die Sekante zur Tangente. Die Werkzeuge gehen auch an der Integralfunktion F: Die Tangente an F hat die Steigung f(x), Extrema von F liegen, wo f das Vorzeichen wechselt, Wendepunkte bei den Extrema von f.
- **Tangente mit Term:** Koppel bei der Tangente *x folgt Parameter* an einen Parameter und animiere ihn mit *Wert ändern* – die Tangente wandert am Graphen. Unter *Beschriftung* wählst du *Term* (`t(x) = 1.50x − 0.25`), *Gleichung* oder *Steigung*; die Beschriftung läuft mit und zeigt immer den aktuellen Wert. Soll die Beschriftung erst später erscheinen oder eigens hervorgehoben werden, klicke bei der Tangente (auch bei Sekante, Punkt am Graphen oder Fläche) auf *Wert als eigene Beschriftung*: Die *Wertbeschriftung* ist ein eigenes Objekt mit eigenen Animationen, folgt aber dem Werkzeug. Bei einer Fläche zeigt sie den Flächeninhalt oder das Integral, bei einem Punkt die Koordinaten oder den Funktionswert; mit *Verschieben* rückst du sie zur Seite. Fertiges Beispiel: Vorlage *Tangente wandert am Graphen*.
- **Mengenform:** Wähle zwei geschlossene Formen (Kreis, Rechteck, Vieleck, Stern, Ring …) und klicke in der Objektbibliothek auf *Mengenform*. Sie zeigt Vereinigung, Schnittmenge, Differenz oder symmetrische Differenz der beiden Formen und folgt ihnen, wenn sie sich bewegen. Ohne Auswahl bringt sie zwei überlappende Kreise mit. Fertiges Beispiel: Vorlage *Mengen: Schnitt und Differenz*.
- **Abbildungen der Ebene:** *Komplexe Abbildung f(z)* bildet jeden Punkt z = x + iy auf f(z) ab (z. B. `z^2`, `exp(z)`, `1/z`, `(z - 1)/(z + 1)`; `i` ist die imaginäre Einheit), *Punktweise Abbildung* auf (x′, y′) mit zwei Termen in x und y. Am eindrucksvollsten mit einer Zahlenebene; unter *Zahlen* wird sie zur komplexen Ebene mit 1, 2 … und i, 2i … Nach einer solchen Abbildung behält das Objekt seine neue Form an seinem Platz (bewegen geht danach nicht mehr). Fertiges Beispiel: Vorlage *Komplexe Abbildung w = z²*.
- **Farbverlauf:** Kreise, Rechtecke, Vielecke, Sterne, Sektoren, Ringe, Linien und Bögen haben unter *Farbverlauf* die Wahl *Füllung*, *Rand* oder beides. Die erste Farbe ist die normale Farbe, dazu kommen eine *Zweite Farbe* und die *Verlaufsrichtung*, in der die zweite Farbe liegt (Manims Standard: oben links). Der Verlauf dreht sich mit dem Objekt; *Farbe ändern* macht es wieder einfarbig.
- **Gestrichelt:** Kreis, Ellipse, Bogen, Quadrat, Rechteck, Dreieck, n-Eck, Vieleck, Stern und Sektor haben die Option *Gestrichelt* mit *Anzahl Striche* und *Strichanteil* (Manims `DashedVMobject`), ebenso Funktionsgraphen (auch Ableitungen, Integralfunktionen, Parameter- und Polarkurven); die Werkzeuge am Graphen funktionieren dann weiter. Eine gestrichelte Form zeigt nur ihren Rand, ohne Füllung; für einen gefüllten Hintergrund legst du eine zweite, ungestrichelte Form darunter. Verwandeln, als Pfad benutzen und Mengenformen gehen mit gestrichelten Formen nicht (Manim hat dann nur die einzelnen Striche).
- **Bogenbahn:** Bei *Bewegen* und *Verwandeln* (auch *Ersetzen* und *Aus Kopie verwandeln*) legt *Bogenbahn (°)* fest, dass jeder Punkt auf einem Kreisbogen zum Ziel läuft statt geradeaus (Manims `path_arc`): 90° ist ein Viertelkreis, 180° ein Halbkreis, positive Werte gehen gegen den Uhrzeigersinn, negative im Uhrzeigersinn. Die Bühne zeigt den Bogen als Bewegungspfad des Schritts.
- **Tabellenzellen hervorheben:** Eine *Hervorhebung* mit einer Tabelle als Ziel bekommt *Tabellenzeile* und *Tabellenspalte*: Zeile 2 und Spalte 3 rahmt genau diese Zelle, Zeile 3 mit Spalte 0 die ganze dritte Zeile, Spalte 1 mit Zeile 0 die erste Spalte. Mit *Abstand* 0 liegt der Rahmen genau auf den Zellgrenzen; als *Hintergrund* liegt die Farbe hinter den Einträgen. Nacheinander ein- und ausgeblendet, wandert die Hervorhebung durch eine Wertetabelle.
- **Lupe:** *Lupe (Zoom)* unter *Medien* legt einen Rahmen auf die Bühne; die Anzeige daneben zeigt seinen Inhalt vergrößert (Manims ZoomedScene). *Einblenden* lässt die Anzeige aus dem Rahmen springen, *Bewegen* verschiebt den Rahmen, *Skalieren* zoomt (kleiner Rahmen = stärkere Vergrößerung). Eine Lupe pro Szene, nur in 2D.
- **Kopplung:** Im Eigenschaften-Panel unter *Kopplung* kann ein Objekt einem anderen folgen (z. B. eine Beschriftung neben einem wandernden Punkt; auch die Kamera kann folgen) oder seine Position aus einer Formel mit Parametern nehmen, etwa `x = 2 cos(w)`, `y = 2 sin(w)`.
- **Funktionsterme:** erlaubt sind `x`, Zahlen (auch `0,5`), `+ - * / ^`, Klammern, implizite Multiplikation (`2x`, `3sin(x)`), `pi`, `e` und die Funktionen `sin cos tan asin acos atan sinh cosh tanh exp log ln log10 log2 sqrt abs floor ceil sign`.

## Tastenkürzel

**F1** zeigt alle Tastenkürzel. Die wichtigsten:

| Aktion | Kürzel |
|---|---|
| Rückgängig / Wiederholen | Strg+Z / Strg+Y |
| Duplizieren / Löschen | Strg+D / Entf |
| Neuer Schritt / Warte-Schritt | Strg+T / Strg+W |
| Vorheriger / nächster Schritt | Bild↑ / Bild↓ |
| Auf der Bühne abspielen | Leertaste |
| Vorschau / ab gewähltem Schritt | F5 / Strg+F5 |
| Exportieren / Skript exportieren | Strg+E / Strg+Umschalt+E |
| Gruppieren / Gruppe auflösen | Strg+G / Strg+Umschalt+G |
| Einpassen / Auf Auswahl zoomen | Strg+0 / Strg+Umschalt+0 |

## Export

*Datei → Exportieren …* bietet MP4, WebM, MOV, GIF und PNG (Ende der Szene oder Zustand nach einem Schritt) in 480p bis 4K oder eigener Größe, auch mit transparentem Hintergrund (MOV, WebM, PNG). Mehrere Szenen lassen sich einzeln oder als ein Gesamtvideo exportieren; Abschnitte, Untertitel (`.srt`) und Ton pro Schritt sind möglich.

*Datei → Skript exportieren (.py) …* speichert das Manim-Skript. Es läuft auch ohne Manim Studio:

```bash
manim -pql meine_szene.py Szene1
```

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| „Manim ist im eingestellten Python-Interpreter nicht installiert“ | `pip install manim` in der verwendeten Umgebung ausführen oder unter *Bearbeiten → Einstellungen … → Python für Manim* den richtigen Interpreter wählen. |
| Formeln erscheinen nur als grauer Quelltext | LaTeX fehlt (`latex` und `dvisvgm` müssen im PATH liegen) oder die Formel enthält einen Fehler; der Hinweis im Eigenschaften-Panel nennt den Grund. |
| Rendern schlägt fehl | Die Meldung nennt die Ursache; das vollständige Log steht im Tab *Render-Log*. |
| Unter Linux startet die App nicht (Qt-Plattform-Fehler) | Fehlende Qt-Bibliotheken installieren, z. B. `sudo apt install libxcb-cursor0`. |
| `pip install` scheitert bei `manimpango` oder `pycairo` | Die Entwicklerpakete von Cairo/Pango fehlen (siehe Installation). |

Fehler und Ideen gern als [Issue auf GitHub](https://github.com/Billi-Bons-minions/Ganim/issues). Hinweise für Mitwirkende stehen in [CONTRIBUTING.md](../CONTRIBUTING.md) (englisch).
