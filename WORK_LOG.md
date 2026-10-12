# Arbeitsprotokoll (Nachtschicht)

> **Push erledigt (12.10., morgens):** Nach `gh auth login` wurde `main` nach
> `Billi-Bons-minions/Ganim` gepusht. Der Push war ein Fast-Forward, alle Commits der Nacht sind auf GitHub.
> Die Abschnitte zu „Push blockiert“ weiter unten beschreiben den Stand während der Nacht.

Hier stehen Entscheidungen, die ich ohne Rückfrage getroffen habe, mit Begründung
und den Punkten, die du prüfen solltest. Neueste Einträge unten.

## Phase 1: Push nach Ganim

### Ziel-Repo
- **Entscheidung:** Ziel ist `https://github.com/Billi-Bons-minions/Ganim`.
- **Warum:** Das ist das einzige öffentliche Repo „Ganim“, das am 11.10. erstellt wurde. Die Beschreibung lautet „Vibe Coded Gui for Manim“, und der Initial-Commit trägt deine E-Mail-Adresse.
- **Remote-Name lokal:** `ganim`.

### Prüfung auf Secrets
- **Was geprüft wurde:** alle 14 Commits auf allen Branches, Arbeitsbaum und Historie.
- **Gesuchte Muster:** API-Keys, Tokens (`ghp_`, `sk-`, `AKIA` …), private Schlüssel, `.env`- und Schlüsseldateien, `/home/minions`-Pfade, E-Mail-Adressen.
- **Ergebnis:** Nichts gefunden.
- **Dateien in der Historie:** nur `.py`, `README.md`, `pyproject.toml`, `requirements.txt`, `.gitignore`.
- **Größte Datei:** `main_window.py` mit ca. 73 KB. Es gibt keine Render- oder Build-Artefakte.

### `.gitignore`
- Neu ignoriert werden:
  - Render-Ausgaben (`*.mp4`, `*.gif`, `media/` …)
  - Logs
  - `.env*`, Schlüsseldateien, `secrets/`
  - Editor- und OS-Dateien

### Zusammenführung
- **Ausgangslage:**
  - Im Remote lag nur der Initial-Commit mit einer zweizeiligen README.
  - Die lokale Arbeit lag auf dem Branch `ausbau`, `main` war der v1-Stand.
- **Vorgehen:**
  1. Lokales `main` per Fast-Forward auf `ausbau` gebracht.
  2. `ganim/main` mit `--allow-unrelated-histories` eingemergt. Kein Force-Push, keine Historie umgeschrieben.
- **README-Konflikt:** Die ausführliche lokale README bleibt. Die Ganim-Beschreibung steht als Untertitel darin.
- **Ab jetzt** wird direkt auf `main` gearbeitet. `ausbau` bleibt lokal als alter Stand stehen.

### Offene Punkte für dich
- **E-Mail-Adresse:** Alle Commits tragen `minions.duke.minions@gmail.com` als Autor. Diese Adresse ist damit öffentlich sichtbar.
  - Wenn du das nicht willst, kannst du für künftige Commits die GitHub-noreply-Adresse setzen.
  - Alte Commits lassen sich nur durch Umschreiben der Historie ändern. Das habe ich bewusst nicht gemacht.
- **Phase 7c:** Den Rest aus dem v2-Plan habe ich nicht gemacht: PyInstaller-Builds, CI und README-Überarbeitung. Laut deiner Anweisung übernimmt das Polieren zum Release die Cloud-Session.

### Push
- **Ergebnis:** Blockiert. Siehe Hinweis ganz oben.
- **Warum blockiert:** Ich habe keine Zugangsdaten gesucht oder angelegt (kein Token, keine Anmeldung im Browser). Das ist deine Entscheidung.
- **Ab jetzt:** Nach jedem Feature versuche ich `git push ganim main` erneut.

## Phase 2: Bestandsaufnahme (12.10., nachts)

### Was geprüft wurde
- **Testsuite:** 300 Tests grün.
- **E2E in der echten App (offscreen):**
  - 5 Vorlagen geladen und jeweils eine Vorschau gerendert.
  - Export als MP4 (720p und 4K), GIF und PNG funktioniert.
- **Fuzzing:**
  - 100 bis 250 zufällige Bearbeitungssitzungen über den echten Controller: Objekte, Animationen, Ziehen, Schritte, Gruppen, Szenen, Rückgängig/Wiederholen.
  - Danach jeweils Speichern/Laden, Codeerzeugung und `manim --dry_run` der erzeugten Skripte.

### Gefunden und behoben
1. **Transparenter Export mit MP4:** brach mit Manim 0.22 ab. Behoben, außerdem WebM und MOV neu als Formate.
2. **Inspektor:** stürzte bei veralteter Mehrfachauswahl ab (z. B. nach Rückgängig).
3. **Aufnahme:** konnte unpassende Animationen erzeugen, z. B. „Bewegen“ für einen Parameter.
4. **Gleichzeitige Animationen:**
   - Problem: Mehrere Animationen eines Objekts im selben Schritt, die Manim nicht gleichzeitig kann (Verwandeln + Bewegen, Erstellen + Wackeln, zwei Verwandlungen derselben Quelle). Teils meldete die Validierung nichts, und erst Manim stürzte ab.
   - **Entscheidung:** eine gemeinsame Regel für Validierung, Codegen und Bedienung. Beim Hinzufügen kommt die Animation in so einem Fall automatisch in einen eigenen Schritt, mit Hinweis.
5. **Abhängige Objekte (Tangente, Fläche, Datenpunkte, 3D-Fläche) ohne Achsen oder Graph:**
   - Vorher entstanden verwaiste Objekte, die dann nicht renderten.
   - **Entscheidung (wie GeoGebra):**
     - Fehlende Achsen bzw. Graphen werden beim Einfügen mit angelegt.
     - Beim Löschen eines Hosts werden die abhängigen Objekte mitgelöscht, mit Hinweis. Rückgängig stellt alles wieder her.
6. **Manim-Laufzeitfehler:**
   - Pfeil nach „Verwandeln“ in eine Gruppe oder einen Text
   - Bewegung entlang einer gestrichelten Linie
   - Gruppe mit einem Parameter darin

### Plan für die Features (Reihenfolge)
1. Neue Animationen:
   - Wachsen vom Rand
   - Rückwärts schreiben
   - Kopie verwandeln
   - Lichtlauf
   - Ausbreiten
   - Tippen mit Cursor
   - Ein- und Ausblenden mit Zoom
2. Hervorhebungs-Objekte, die an einem Objekt hängen: Rahmen, Hintergrund, Unterstreichen, Durchstreichen.
3. Winkelmarkierung zwischen zwei Linien.
4. Bewegungsspur (TracedPath).
5. Vektorfeld und Stromlinien.
6. 3D-Körper: Kugel, Würfel, Kegel, Zylinder, Torus …
7. Implizite Kurven f(x, y) = 0.
8. Mehr Vorlagen und Beispielszenen.
9. Wenn Zeit bleibt: Netzwerk-Graph, Aufzählungslisten, Kamera-Zoom auf ein Objekt.

## Phase 2: Umsetzung (Entscheidungen)

Alle Features sind mit echten Manim-Läufen getestet. Wo die Bühne etwas nachzeichnet, habe ich sie per Bildvergleich gegen Manim geprüft.

### Markierung (Rahmen, Hintergrund, Unterstreichen, Durchstreichen)
- **Entscheidung:** Die Markierung folgt ihrem Ziel immer (`always_redraw`).
- **Folge:** Deshalb sind Bewegen/Skalieren/Farbe als Animation der Markierung selbst nicht erlaubt. Man bewegt das Ziel.

### Spur (TracedPath)
- **Entscheidung:** „Einblenden“ einer Spur wird im Skript zu `self.add(spur)`.
- **Warum:** `FadeIn` auf TracedPath stürzt in Manim 0.22 ab.

### „Kopie verwandeln“
- **Entscheidung:** Erzeugt `ReplacementTransform(quelle.copy(), ziel)` statt `TransformFromCopy`.
- **Warum:** Gleiches Bild, aber Manims TransformFromCopy formt das Ziel um und macht z. B. Pfeile unbrauchbar.

### Kamera
- **2D:** Drehen der Kamera ist verboten, weil Manims MovingCamera das Bild nur verzerrt.
- **3D:**
  - Kamerafahrten gehen über einen unsichtbaren Steuerrahmen (`studio_camera_frame`).
  - Der verbundene Export mit 3D-Szenen nutzt `ThreeDScene` und setzt für 2D-Teile die Draufsicht.

### Abhängige Objekte (wie GeoGebra)
- Fehlende Hosts werden beim Einfügen angelegt.
- Beim Löschen des Hosts wird mitgelöscht.
- Beim Einfügen in eine andere Szene kommen fehlende Hosts mit.

### Gleichzeitige Animationen
- **Regel:** Pro Objekt nur kombinierbare Animationen im selben Schritt (`types.simultaneous_conflicts`).
- **Folge:** Sonst kommt die neue Animation automatisch in einen eigenen Schritt.

### Vektorfelder
- Pfeile mit Parametern nutzen `always_redraw`.
- Stromlinien nehmen den Parameterwert beim Start (`always_redraw` wäre dafür zu langsam).

### 3D-Körper
- Platzierung in Koordinaten der 3D-Achsen; Größen in Szenen-Einheiten (wie Manim).
- Bewegen und Drehen sind als Animation nicht erlaubt; Skalieren und Farbe gehen.

### Offene Punkte
- **Spuren mit „Verblassen“:** Bleibt das Objekt stehen, bleibt in Manim ein kurzer Rest-Schweif sichtbar. Das ist Manims Verhalten.
- **Riesige Transforms:** Ein Transform eines sehr detaillierten Objekts, etwa einer 3D-Fläche in Achsen, kann in Manim minutenlang dauern. Das wird nicht abgefangen.

### Hinweise zur Commit-Historie
- **Commit `700809a` (Aufzählungslisten):** Er enthielt einen Zeittest, der unter Last fehlschlug (Stromlinien-Cache < 0,3 s).
  - Ursache: Mein Commit-Befehl hatte den Exit-Status der Tests verschluckt.
  - Behoben in `130d284`.
  - Seitdem wird nur noch committet, wenn Lint und die komplette Suite grün sind.
- **Fuzzing:** 4 Runden mit je 100 bis 150 zufälligen Sitzungen. Alle gefundenen Abstürze sind behoben; die Details stehen in HANDOFF.md.

### Push nach Ganim (Stand am Morgen)
- **Ergebnis:** Weiterhin blockiert, keine GitHub-Zugangsdaten auf dem Rechner. Alle Commits liegen lokal auf `main`.
- **Hochladen:** nach der Anmeldung mit `git push ganim main` (siehe Hinweis oben).

---

# Tagschicht 12.10. (Cloud-Session)

## Rückfragen am Morgen
Ich habe vier Fragen gestellt; ohne Antwort gelten diese Entscheidungen (änderbar):
1. **LICENSE:** MIT mit „Copyright (c) 2026 Billi-Bons-minions“.
2. **Version:** 0.9.0 als erste öffentliche Vorabversion. Die 1.0.0 vergibst du bei der Freigabe.
3. **Installationspakete:** GitHub-Actions-Workflow für PyInstaller, **nur manuell startbar**, veröffentlicht nichts.
4. **README:** auf Englisch (internationale Sichtbarkeit), mit Hinweis auf die deutsche Oberfläche.

## Bestandsaufnahme
- **Umgebung:** Python 3.13, Manim 0.22.0, PySide6 6.12, TeX Live, FFmpeg 9.
- **Tests:** 354 grün. Die Suite brauchte 10 Minuten, weil geschlossene Testfenster nie gelöscht wurden und jedes neue Stylesheet alle alten Fenster neu stylte. Behoben, jetzt ca. 4 Minuten.
- **App-Start:** Die App startet mit Willkommensdialog und lässt sich sauber schließen; das gilt auch für eine frische Installation per `pip install .` in eine leere venv.
- **Alle 10 Vorlagen** über die echte App als Vorschau gerendert; Endbilder angesehen.
- **Fehlerfälle geprüft:**
  - Manim fehlt im Interpreter → klare Meldung mit Lösung.
  - LaTeX fehlt → wird vor dem Rendern erkannt und erklärt (Deutsch und Englisch).
  - Ungültige Formel → Meldung nennt jetzt LaTeX-Fehler **und** Formel (vorher nur „Prüfe die Formeln“).

### Gefunden und behoben
- Beschriftungen von Null- und Extrempunkten überlappten sich und die Kurve. Jetzt: Hochpunkt oben, Tiefpunkt unten, sonst auf der Seite ohne Kurve. Bühne und Video gleich.
- Zeitleiste zeigte „+ + Schritt“ und „+ + Warten“ (Symbol plus Text).
- Vorlagen „Parameter“ und „Kegelschnitte“: Zahl klebte an „a =“ bzw. „r =“.
- Die App startete immer auf Deutsch. Jetzt folgt die Sprache beim ersten Start der Systemsprache (Deutsch oder sonst Englisch).

### Offen aus der Bestandsaufnahme
- Das README beschreibt noch den Stand von Version 1 (viele Funktionen fehlen darin, Testzeiten stimmen nicht).
- `pyproject.toml` hat Version 1.0.0, es fehlen Lizenz, Projekt-URLs und Klassifizierer.
- `examples/` enthält nur ein Erweiterungsbeispiel, keine Beispielprojekte.
- Kein CI, keine LICENSE, kein CHANGELOG, kein CONTRIBUTING.

## Neue Funktionen (Tagschicht)

### Knoten/Kanten hervorheben (Netzwerke)
- **Was:** Eine neue Animation färbt einzelne Knoten und Kanten ein (dauerhaft), lässt sie kurz aufleuchten oder aufblitzen. Die Teile werden als Text angegeben, z. B. `A, A-B, B`.
- **Entscheidungen:**
  - In ungerichteten Netzen ist `B-A` dieselbe Kante wie `A-B`. Ein Knotenname hat Vorrang vor einer Kanten-Lesart (`A-1` kann ein Knoten sein).
  - Beim Einfärben bleibt die Beschriftung im Knoten in ihrer Farbe (`set_fill(..., family=False)`). Beim Aufleuchten wird nur der Kreis kurz größer und farbig, statt Manims `Indicate` zu verwenden, das auch den Buchstaben einfärbt.
  - Aufblitzen: Knoten mit `Flash`, Kanten mit einem Lichtlauf (`ShowPassingFlash`).
- **Offen:** Der Skript-Import kennt Netzwerke grundsätzlich nicht (war schon vorher so); solche Zeilen werden mit Hinweis übersprungen.

### Lineare Abbildung (ApplyMatrix)
- **Was:** Eine 2×2-Matrix verformt Gitter, Vektoren, Formen und Texte um den Ursprung (3Blue1Brown-Stil). Dazu gibt es die Vorlage „Lineare Abbildung (Scherung)“.
- **Entscheidungen:**
  - Die Bühne speichert die Matrix im Zustand des Objekts und zeichnet sie exakt; späteres Drehen, Skalieren und Bewegen funktionieren weiter (mit Manim per Bildvergleich geprüft).
  - Nicht erlaubt für Objekte, die Manim in jedem Bild neu zeichnet (Markierungen, Graph-Werkzeuge, Winkel, Spuren, 3D), weil die Verformung dort verloren ginge.
- **Hinweis:** Vorlagen müssen ohne LaTeX laufen (bestehender Test). Die Matrix steht deshalb in der Vorlage als Text „(x, y) ↦ (x + y, y)“.

### Kopplung (Updater)
- **Was:** Neuer Abschnitt „Kopplung“ im Eigenschaften-Panel: Ein Objekt folgt einem anderen (z. B. Beschriftung neben einem wandernden Punkt) oder nimmt seine Position aus einer Formel mit Parametern (z. B. `2 cos(w)`, `2 sin(w)`).
- **Entscheidungen:**
  - Der Abstand beim Folgen ist der Abstand, den man am Anfang auf der Bühne einstellt. Ziehen an der Startposition ändert ihn.
  - Für gekoppelte Objekte sind Bewegen, Pfad, Tauschen, Matrix und Verwandeln gesperrt, mit Erklärung, weil der Updater sie überschreiben würde.
  - Beim Einschalten springt nichts: „Formel“ übernimmt die aktuelle Position als Zahlen, „Folgt“ wählt das nächstgelegene passende Objekt.
- **Bekannte Grenze:** Während ein gekoppeltes Objekt selbst animiert wird (z. B. Drehen), pausiert Manim seinen Updater. Bewegt sich das Ziel genau in diesem Moment, springt das Objekt danach nach.

### Vorlagen
- Neu: „Präsentationsfolie“, „Graphentheorie: ein Weg“ (nutzt die Hervorhebung) und „Lineare Abbildung (Scherung)“.

### Werkzeug: Fuzzer
- `tools/fuzz_sessions.py` spielt zufällige Bearbeitungssitzungen über den echten Controller ab und prüft danach Speichern/Laden, die Bühne, die Codeerzeugung und `manim --dry_run`.
- Ein Wächter schließt modale Dialoge und protokolliert sie (vorher hing eine Sitzung an einem Dialog).

## Release-Vorbereitung (Tagschicht)

### Entscheidungen
- **Version 0.9.0:** erste öffentliche Vorabversion. Die einzige Quelle ist `manim_studio.__version__`; `pyproject.toml` liest sie von dort.
- **MIT-Lizenz:** Alle Abhängigkeiten erlauben MIT für den App-Code (Manim MIT, numpy/networkx/PyAV BSD). PySide6 steht unter LGPL-3.0; das ist als Bibliothek unproblematisch. Bei gebündelten Apps gelten für PySide6 die LGPL-Pflichten (steht im README).
- **README auf Englisch**, dazu eine deutsche Anleitung in `docs/ANLEITUNG.md` (Installation, erste Animation, Begriffe, Kürzel, Fehlerbehebung).
- **Installation:** `pip install git+https://github.com/Billi-Bons-minions/Ganim`. In frischen Umgebungen geprüft (venv mit Python 3.13; Start über `manim-studio`).
- **Python 3.10 bis 3.13** und Manim 0.19 bis 0.22. Zwei Funde dabei:
  - PySide6 6.12 stürzt unter Python < 3.12 ab („deallocating None“, ein PySide-Fehler, nachgestellt in 3 Zeilen). Dort wird jetzt PySide6 < 6.12 installiert.
  - Manim 0.19 schreibt bei PNG eine Bildfolge. Der PNG-Export nutzt jetzt `-s`.
- **CI:** Lint plus alle Tests inkl. echter Manim-Läufe unter Python 3.10 (ohne LaTeX) und 3.13 (mit LaTeX). Der erste Lauf fand einen echten Fehler: Eine Zahl mit Einheit braucht LaTeX. Das wird jetzt vor dem Rendern erklärt.
- **App-Bündel (PyInstaller):** Nur experimentell und nur als manuell startbarer Workflow (`bundle.yml`). Das gebündelte Programm beantwortet die internen Aufrufe `-m manim` und `-c` selbst. Unter Linux geprüft (Start, Systemprüfung, Rendern); **Windows und macOS sind ungetestet**. Der Workflow rendert nach dem Bau eine Testszene, sodass ein Lauf das zeigt.

### Was ich nicht gemacht habe (deine Freigabe)
- Kein Tag, kein GitHub-Release, kein PyPI. Repo-Einstellungen (Beschreibung, Topics) habe ich nicht angefasst.

---

# Zusammenfassung der Tagschicht (12.10.)

## Fertig und getestet
- **Bestandsaufnahme:** Das Repo war vollständig, und alle 354 Tests waren grün. Die App startet, alle Vorlagen rendern, die Fehlerfälle (Manim fehlt, LaTeX fehlt, kaputte Formel) melden sich verständlich.
- **Korrekturen:**
  - Punktbeschriftungen überlappen nicht mehr.
  - Die Sprache folgt beim ersten Start dem System.
  - LaTeX-Fehler nennen die Formel.
  - Lange Titel und Namen im Eigenschaften-Panel werden richtig angezeigt.
  - Doppeltes „+ +“ in der Zeitleiste ist weg.
  - Die Testsuite braucht 4 statt 10 Minuten.
- **Neue Funktionen**, jeweils mit Bühne = Video geprüft und mit echten Manim-Tests:
  - Knoten/Kanten eines Netzwerks hervorheben
  - Lineare Abbildung (`ApplyMatrix`)
  - Kopplung (Updater): Objekte folgen einem Objekt oder einer Formel; auch die 2D-Kamera kann folgen
  - 3D-Pfeile, -Strecken und -Punkte
  - Drei neue Vorlagen (jetzt 13)
- **Fuzzing:** Neuer Fuzzer `tools/fuzz_sessions.py`.
  - Runde 5 (49 Sitzungen) fand einen Absturz: Zahlen bzw. Graphen, die von einem Parameter abhängen, während der Parameter sich im selben Schritt ändert. Behoben, plus neue Regel `model/conflicts.py`.
  - Runde 6: siehe unten.
- **Release-ready:** Version 0.9.0, LICENSE, README mit echten Renderings, deutsche Anleitung, CHANGELOG, CONTRIBUTING, CI (grün), `examples/` mit 7 Projekten, `.gitignore`.
- **Stand am Ende:** 390 Tests grün unter Python 3.13 (Manim 0.22, mit LaTeX) und Python 3.10 (Manim 0.19, ohne LaTeX).

## Nicht fertig / bekannte Grenzen
- **App-Bündel** für Windows/macOS ungetestet (siehe oben). Ohne Bündel braucht man Python zur Installation.
- **Skript-Import:** kennt Netzwerke und 3D-Vektoren nicht (Zeilen werden mit Hinweis übersprungen).
- **Kopplung:** Wird ein gekoppeltes Objekt selbst animiert, pausiert Manim dessen Updater für diese Zeit.
- **Polarkoordinaten-Gitter und nichtlineare Abbildungen** (`ApplyComplexFunction`) habe ich bewusst nicht angefangen. Sie würden die Zuordnung von Graphen zu Gittern an vielen Stellen ändern.
- Ältere Punkte aus der Nacht gelten weiter (Rest-Schweif bei verblassenden Spuren, sehr detaillierte Transforms können lange dauern).

## Deine Entscheidungen
1. **Freigabe:**
   - Soll ich einen Tag `v0.9.0` und ein GitHub-Release anlegen? Oder willst du gleich `1.0.0`? Dann nur `__version__` und CHANGELOG ändern.
2. **PyPI:**
   - Soll das Paket auf PyPI? Dann ginge `pip install manim-studio`.
   - Vorher prüfen, ob der Name `manim-studio` dort frei ist; sonst einen anderen wählen (z. B. `ganim`).
3. **App-Bündel:** Bitte einmal *Actions → App bundles (experimental) → Run workflow* starten. Wenn Windows/macOS grün sind, können wir sie als Downloads anbieten.
4. **Lizenzinhaber:** In der LICENSE steht „Billi-Bons-minions“. Möchtest du einen echten Namen?
5. **E-Mail in Commits:** Die Commits der Nacht tragen deine Gmail-Adresse und sind öffentlich (siehe oben). Für künftige Commits kannst du die GitHub-noreply-Adresse setzen.
6. **Repo-Einstellungen auf GitHub** (macht nur du): Beschreibung, Website, Topics (z. B. manim, animation, math, education), Issues aktivieren.
