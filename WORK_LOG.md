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

### Weitere Funktionen (Nachmittag)
Jede Funktion ist mit einem Vergleich Bühne ↔ Manim-Bild und mit echten Manim-Tests unter Manim 0.19 und 0.22 geprüft.
- **Wertetabelle** zum Funktionsgraphen (Knopf im Eigenschaften-Panel).
- **Polar-Gitter** als Option des Koordinatengitters (Kreise und Strahlen, `PolarPlane`).
- **Implizite Kurven 3× schneller:** `y` wurde fälschlich als Parameter gezählt, deshalb wurde die Kurve in jedem Bild neu berechnet (Fund aus Fuzz-Runde 6).
- **Sekante** als Graph-Werkzeug: Gerade durch f(x₀) und f(x₀ + h) mit Steigungsdreieck; x₀ und h können an Parameter gekoppelt sein.
  - Entscheidung: Bei h = 0 zeichnen Bühne und Skript die Tangente (statt eines Fehlers). So kann man h gegen 0 animieren, und das letzte Bild zeigt die Tangente.
  - Das Eigenschaften-Panel zeigt den Differenzenquotienten live.
- **Vorlage „Von der Sekante zur Tangente“** (jetzt 14 Vorlagen), auch im Beispielprojekt `function-analysis.msproj`, und als GIF im README (ersetzt „Parameter erkunden“).
- **Platonische Körper** (Tetraeder, Oktaeder, Ikosaeder, Dodekaeder) als weitere Formen des 3D-Körpers, mit Kantenlänge und wahlweise sichtbaren Ecken.
  - Entscheidung: Manim zeigt die Ecken standardmäßig als kleine Kugeln; die App blendet sie aus, außer man schaltet „Ecken zeigen“ ein.
  - Die Bühne zeichnet Flächen und Ecken einzeln von hinten nach vorn, damit vordere Flächen die hinteren verdecken wie bei Manim.
- **3D-Reihenfolge wie in Manim:** Achsen, Flächen, Körper und 3D-Pfeile zeichnet die Bühne jetzt nach ihrer Tiefe (vorher in Ebenen-Reihenfolge), 3D-Kurven und Texte darüber, wie Manims `ThreeDCamera`.
- **Gebogener Pfeil** (`CurvedArrow`, `CurvedDoubleArrow`, `ArcBetweenPoints`) als eigene Objektart.
  - Entscheidung: eine neue Objektart statt einer Biegung für die vorhandenen Linien, weil gerade Linien an vielen Stellen vorausgesetzt werden (Endpunkt-Griffe, Winkelmarken, Pfade).
  - Die Bühne rechnet Manims Schritte nach (Bézierpunkte, Spitze entlang der Tangente, Bogen bis zur Spitze verkürzt, beim Doppelpfeil die zusätzliche Abbildung). Ein Test vergleicht alle Punkte mit Manim (Abweichung < 10⁻⁶).
  - „Pfeil wachsen lassen“ (GrowArrow) ist dafür gesperrt: Manim kann es nur für gerade Pfeile (Test hat es gefunden).
  - Der Skript-Import liest gebogene Pfeile.

### Gefunden und behoben (Nachmittag)
- **Absturz mit Manim 0.19:** Gestrichelte Hilfslinien der Länge 0 (ein Punkt am Graphen auf einer Achse, z. B. bei x = 0, oder eine Sekante mit h = 0) brachen das Rendern ab. Das Skript nutzt jetzt `studio_dashed_line`/`studio_lines_to_point`. Der Fehler bestand schon vorher beim „Punkt am Graphen“.
- **Namenskonflikt im Skript:** Ein Parameter namens `x0` oder ein Objekt namens „Studio Plot“ verdeckte Variablen bzw. Hilfsfunktionen des erzeugten Skripts. Solche Namen bekommen jetzt einen Zusatz (`x0_obj`).
- **Formelfehler erst beim Rendern (Fuzz-Runde 7):** Ein LaTeX-Text (`Tex`) mit Mathematik ohne `$…$` ließ das Rendern scheitern, obwohl die Bühne den Fehler schon kannte. Jetzt stoppen Vorschau und Export vorher mit der LaTeX-Meldung. Nur Fehler, die LaTeX selbst meldet, blockieren (nicht z. B. eine Zeitüberschreitung); der Formel-Cache unterscheidet jetzt Text- und Mathe-Modus.
- **README versprach zu viel beim Skript-Import:** Es stand dort, der Import verstehe den Code, den Manim Studio schreibt. Er liest aber nur einfache Szenen (Formen, Linien und Pfeile, Text, Achsen, einfache Graphen, Zahlen, Gruppen, übliche Animationen); vieles andere wird übersprungen und aufgelistet. README und CHANGELOG sagen das jetzt so.

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
  - Wertetabelle, Polar-Gitter
  - Sekante mit Steigungsdreieck (h → 0 wird zur Tangente)
  - Platonische Körper (Tetraeder, Oktaeder, Ikosaeder, Dodekaeder)
  - Gebogener Pfeil (`CurvedArrow`, `CurvedDoubleArrow`, `ArcBetweenPoints`)
  - 3D-Objekte auf der Bühne nach Tiefe sortiert wie in Manim
  - Vier neue Vorlagen (jetzt 14), darunter „Von der Sekante zur Tangente“
- **Fuzzing:** Neuer Fuzzer `tools/fuzz_sessions.py`.
  - Runde 5 (49 Sitzungen) fand einen Absturz: Zahlen bzw. Graphen, die von einem Parameter abhängen, während der Parameter sich im selben Schritt ändert. Behoben, plus neue Regel `model/conflicts.py`.
  - Runde 6 (117 Sitzungen, dann Zeitlimit): kein Absturz, 2 zu langsame Szenen. Eine davon (implizite Kurve) ist jetzt 3× schneller; die andere ist eine Manim-Grenze (siehe unten).
  - Runde 7 (Stand vom Nachmittag, 80 Sitzungen, davon 55 mit echtem Manim-Lauf): 79 in Ordnung, 1 Fund: Ein LaTeX-Text mit Mathematik ohne `$…$` scheiterte erst beim Rendern. Behoben, Vorschau und Export stoppen jetzt vorher mit der LaTeX-Meldung.
- **Release-ready:** Version 0.9.0, LICENSE, README mit echten Renderings, deutsche Anleitung, CHANGELOG, CONTRIBUTING, CI, `examples/` mit 9 Projekten, `.gitignore`. Frische Installation per `pip install git+https://github.com/Billi-Bons-minions/Ganim` am Nachmittag erneut geprüft: App startet, Vorlage rendert.
- **Stand am Ende:** 428 Tests grün unter Python 3.13 (Manim 0.22, mit LaTeX); unter Python 3.10 (Manim 0.19, wirklich ohne LaTeX) 425 grün und 3 übersprungen, weil sie LaTeX brauchen. CI (Lint und beide Testläufe) ist für den letzten Code-Stand grün.

## Nicht fertig / bekannte Grenzen
- **App-Bündel** für Windows/macOS ungetestet (siehe oben). Ohne Bündel braucht man Python zur Installation.
- **Skript-Import:** liest nur einfache Szenen. Graph-Werkzeuge, 3D, Netzwerke, Vektorfelder und Listen werden übersprungen und aufgelistet. Zum Weiterarbeiten das Projekt als `.msproj` speichern.
- **3D-Reihenfolge auf der Bühne:** Manim sortiert jedes Flächenstück einzeln nach seiner Tiefe; die Bühne sortiert ganze Objekte nach der Tiefe ihres Mittelpunkts. Bei Körpern, die sich durchdringen, oder bei Achsen, die durch einen Körper laufen, kann die Überdeckung deshalb leicht abweichen.
- **Sehr ungleiche Verwandlungen** (z. B. eine Fläche aus 576 Feldern in 3D-Achsen verwandeln) rendern sehr langsam, weil Manim jedes Feld einzeln angleicht. Kein Fehler der App; Fund aus Fuzz-Runde 6.
- **Kopplung:** Wird ein gekoppeltes Objekt selbst animiert, pausiert Manim dessen Updater für diese Zeit.
- **Nichtlineare Abbildungen** (`ApplyComplexFunction`) habe ich bewusst nicht angefangen (Bühne müsste Formen punktweise verbiegen).
- **Polar-Gitter** gibt es jetzt als Option des Koordinatengitters. Das kartesische Koordinatensystem bleibt dabei erhalten, damit Graphen exakt bleiben. Grenze: Bei unsymmetrischen Bereichen (z. B. x von −2 bis 10) passt eine *Bewegen*-Animation des Gitters nicht genau zur Bühne, weil Manim die Mitte inklusive der Kreise berechnet.
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
7. **CI-Hinweis:** GitHub stellt `ubuntu-latest` ab dem 19.10.2026 auf Ubuntu 26 um (Hinweis im CI-Lauf). Falls die CI danach scheitert (z. B. andere Paketnamen für LaTeX/Cairo), in `.github/workflows/ci.yml` `ubuntu-24.04` fest eintragen. Ich habe das bewusst nicht vorab geändert.

---

# Nachtrag: Rückmeldung nach dem Testen

**Dein Anwendungsfall:** Eine Tangente wandert animiert am Graphen entlang, und eine Beschriftung soll ihr folgen und den aktuellen Term zeigen. Das ging bisher nicht.

**Umgesetzt:**
- Tangente und Sekante haben die Option **Beschriftung**: keine, *Term* (`t(x) = 1.50x − 0.25`, bei der Sekante `s(x) = …`), *Gleichung* (`y = …`) oder *Steigung* (`m = …`), dazu Nachkommastellen und Seite.
- Ist x₀ (oder h, oder ein Parameter im Funktionsterm) an einen Parameter gekoppelt, zeichnet Manim die Beschriftung in jedem Bild neu (`always_redraw`). Sie zeigt also immer den aktuellen Term.
- **Entscheidung Position:** am Berührpunkt (bei der Sekante zwischen den beiden Punkten), mit kleinem Abstand neben der Linie. „Automatisch“ legt sie auf die Seite, auf der der Graph nicht verläuft. Am Wendepunkt wechselt sie deshalb die Seite; wer das nicht will, wählt fest „über“ oder „unter der Linie“.
- **Entscheidung Zahlenformat:** feste Nachkommastellen (Standard 2), damit die Breite beim Wandern nicht springt; echtes Minuszeichen „−“, nie „−0.00“.
- Das Skript bekommt dafür zwei kleine Hilfsfunktionen (`studio_term`, `studio_beside`). Die Bühne rechnet genauso; ein Test führt `studio_term` aus und vergleicht mit der Bühne. Ein Manim-Test prüft, dass die Beschriftung am Ende genau neben der Tangente an der neuen Stelle sitzt (Manim 0.19 und 0.22).
- Neue Vorlage **„Tangente wandert am Graphen“** (jetzt 15). Ich habe sie als GIF geprüft. Damit der Term am Anfang und am Ende nicht auf der Achse liegt, läuft die Tangente von x = −1,5 bis 1,5. Unterwegs kreuzt der Term kurz die y-Achse; das lässt sich bei einer wandernden Beschriftung nicht ganz vermeiden.

**Dabei gefunden und behoben:** Folgt ein „Punkt am Graphen“ einem Parameter, zeigte die Bühne `(1.5 | -1)`, das Video aber `(1.50 | -1.00)`. Jetzt zeigen beide zwei feste Nachkommastellen.

**Offen:** Die Beschriftung gehört zur Tangente (gleiche Farbe, erscheint und verschwindet mit ihr). Eine eigene Animation nur für die Beschriftung, z. B. erst später einblenden, geht noch nicht.

## Weitere Punkte nach der Rückmeldung (je ein Commit, erst wenn fertig)

### 1. Zahl zeigt eine Formel aus Parametern
- Die Zahl (DecimalNumber) hat das Feld **Formel**. Ist es gefüllt, zeigt sie live deren Wert, z. B. `a^2/2` oder `sin(a) + 1`. Im Skript wird das ein Updater mit `set_value(...)`, auf der Bühne wird mit denselben Parameterwerten gerechnet.
- Entscheidung: Die Formel hat Vorrang vor „Parameter“ und „Wert“. Sie darf nur Zahlen und Parameter enthalten (kein x). Fehler werden vor dem Rendern gemeldet.
- „Wert ändern“ ist für Zahlen gesperrt, die einem Parameter oder einer Formel folgen. Der Updater würde die Änderung sofort wieder überschreiben.
- Getestet mit einem echten Manim-Lauf unter 0.19 und 0.22: a läuft auf 3, die Zahl zeigt 4.5.
- Offen: Funktionswerte eines Graphen wie `f(a)` gehen in der Formel noch nicht; dafür müsste der Formel-Parser Graphen als Funktionen kennen.

### 2. Integralfunktion
- Neuer Kurventyp **Integralfunktion F(x) = C + ∫ f(t) dt** von a bis x, mit dem Knopf „∫ Integralfunktion“ am Graphen. Untere Grenze a und Konstante C sind einstellbar; hängt f von Parametern ab, wird F live mitgerechnet.
- Entscheidung: numerische statt symbolische Integration, wie Manims `plot_antiderivative_graph`. Im Skript rechnet der Helfer `studio_integral` (Simpson-Regel, 200 Schritte), auf der Bühne eine feine Tabelle. Beides weicht um weniger als 10⁻⁴ ab; ein Manim-Test vergleicht die gezeichnete Kurve mit der Bühne.
- Grenze: Auf einer Integralfunktion gibt es keine Graph-Werkzeuge (Tangente, Nullstellen …), weil diese einen Funktionsterm brauchen. Die Knöpfe sind dort ausgegraut. Ist f irgendwo nicht definiert, endet F dort.

### 3. Parameterflächen
- Eine 3D-Fläche hat jetzt die Form „z = f(x, y)“ oder „Parameterfläche x(u, v), y(u, v), z(u, v)“. Voreinstellung ist eine Kugel mit Radius 2; Bereiche für u und v sind einstellbar, Parameter in den Formeln werden live mitgerechnet (`always_redraw`).
- Die Bühne zeichnet Parameterflächen Feld für Feld von hinten nach vorn (ein Torus hat ein Loch und überlappt sich selbst). Form und Lage stimmen mit Manim überein (Bildvergleich mit einem Torus).
- Grenze: Manim schattiert 3D-Flächen nach einer Lichtquelle; die Bühne zeichnet sie einfarbig. Das gilt für alle 3D-Objekte.

### 4. Formel rechnet ihr Ergebnis aus
- Wunsch: Beim Einfügen einer Formel soll man den Inhalt ausrechnen lassen können, auch mit Parametern.
- Umgesetzt als Option **Ergebnis ausrechnen** an der Formel (plus Nachkommastellen). Das LaTeX wird in einen Rechenterm übersetzt (`model/latex_term.py`: `\frac`, `\cdot`, `\times`, `\div`, `\sqrt`, `^`, `\pi`, sin/cos/tan/ln/log/exp, `\left`/`\right`) und als „= 3.50“ angehängt.
- Mit Parametern rechnet im Skript ein Updater in jedem Bild neu (`become(MathTex(...))`, die Formel bleibt an ihrem Platz). Auf der Bühne wird mit denselben Werten gerechnet.
- Grenzen:
  - Nicht ausrechenbare Formeln (mit x, mit „=“, Integrale …) werden vor dem Rendern gemeldet.
  - Bei einem live gerechneten Ergebnis entfallen eingefärbte Teile.
  - LaTeX setzt für jeden neuen Wert die Formel neu; lange Animationen mit Parametern rendern dadurch langsamer.


---

# Abendschicht 12.10. (lokale Session)

Start: lokales Repo war schon auf dem Stand von GitHub (`0ee67f4`), 458 Tests grün (Python 3.12, Manim 0.22). Für Manim 0.19 habe ich lokal eine zweite venv (Python 3.12) außerhalb des Repos angelegt; jedes neue Feature läuft mit seinen Manim-Tests in beiden Versionen.

**Reihenfolge:** wie in deiner Liste (Nutzen für Mathe-Erklärvideos). Bühne und Video vergleiche ich jeweils mit einem Hilfsskript, das die Bühne als Bild zeichnet und neben `manim -s` legt (liegt nicht im Repo).

## 1. Mengenformen (boolesche Operationen)
- **Was:** Neue Objektart *Mengenform* (Vereinigung, Schnittmenge, Differenz, symmetrische Differenz) aus zwei geschlossenen Formen: Kreis, Quadrat, Rechteck, Dreieck, Ellipse, Vieleck, regelmäßiges Vieleck, Stern, Sektor, Ring oder eine andere Mengenform (verschachtelt). Vorlage *Mengen: Schnitt und Differenz* (jetzt 16 Vorlagen), Skript-Import.
- **Entscheidung: folgt den Formen.** Die Mengenform wird wie Winkel und Markierung in jedem Bild neu berechnet (`always_redraw`). Bewegt, dreht oder verwandelt sich eine Form, ändert sich das Ergebnis mit (z. B. wird die Schnittmenge kleiner, wenn ein Kreis wegrückt). Dafür kann man die Mengenform selbst nicht bewegen, drehen oder umfärben (Meldung wie beim Winkel). Ein- und Ausblenden, Hervorheben usw. gehen.
- **Entscheidung: Bedienung.** Zwei gewählte Formen werden verknüpft; ohne Auswahl bringt die Mengenform zwei überlappende Kreise mit (wie die Graph-Werkzeuge ihre Achsen). Voreinstellung ist die Schnittmenge. Wird eine Form gelöscht, verschwindet die Mengenform mit.
- **Gefunden: Manims `Union` ist fehlerhaft.** Die Funktion legt beide Umrisse zusammen und füllt nach der Umlaufrichtung. Manim zeichnet einen Sektor im Uhrzeigersinn, Kreis, Dreieck und Vielecke gegen den Uhrzeigersinn. Wo sich solche Formen überlappen, entsteht deshalb ein Loch. `Intersection`, `Difference` und `Exclusion` haben das Problem nicht. Das Skript vereinigt deshalb mit einer kleinen Hilfsfunktion `studio_union` (`pathops.op(…, UNION)`, wie Manims übrige Operationen). Video und Bühne zeigen damit die echte Vereinigung. Geprüft mit Manim 0.19 und 0.22.
- **Bühne:** rechnet mit Qt-Pfadoperationen auf den echten Umrissen (Bildvergleich mit Manim: deckungsgleich). Das Modell (ohne Qt) bestimmt den Mittelpunkt des Ergebnisses exakt für Vielecke und Kreise mit 64 Ecken; ein Manim-Test vergleicht Mittelpunkt und Größe (Abweichung < 0,03).
- **Nebenbei behoben:** Bewegungspfade entlang eines regelmäßigen Vielecks mit gerader Eckenzahl begannen an der falschen Ecke, ein Viereck war um 45° gedreht (`paths.py`).
- **Grenzen:** Texte und Formeln können keine Operanden sein (Manim verknüpft nur Formen mit eigenen Punkten, ein Text ist eine Gruppe). Wird die Mengenform im selben Schritt eingeblendet, in dem sich eine ihrer Formen bewegt, folgt sie in Manim erst nach dem Einblenden (Manim pausiert Updater während einer Animation); auf der Bühne folgt sie sofort.

## Fuzz-Runde 8 (20 Sitzungen, nach den Mengenformen)
- 19 in Ordnung, 1 Fund (schon vorher vorhanden): Wird eine Spur (`TracedPath`) ausgeblendet, bevor Manim ein einziges Bild von ihr gezeichnet hat (z. B. gleich im ersten Schritt), stürzt Manim ab (`zip() argument 2 is longer than argument 1`). Lösung: Das Skript gibt der Spur beim Erscheinen sofort ihren ersten Punkt (`spur.update(0)`); das Aussehen ändert sich dadurch nicht.
- Testhilfe: Manim 0.19 legt seinen `Tex`-Ordner ohne übergeordnete Ordner an; bei `--dry_run` fehlte deshalb der Medienordner, und ein Formel-Test schlug nur lokal (0.19 mit LaTeX) fehl. Die App selbst rendert nie mit `--dry_run`; die Testhilfe legt den Ordner jetzt vorher an.

## 2. Funktionswerte von Graphen in Formeln (`f(a)`)
- **Was:** In den Formeln einer Zahl, in Positionsformeln (Kopplung) und beim Ergebnis einer Formel kann man Graphen aufrufen: `f(a)`, `f(2) + 1`, `f(f(a))`, `2f(a)`. Hängt `f` selbst von Parametern ab (z. B. `k x^2`), rechnet die Zahl beim Animieren beider Parameter mit.
- **Entscheidung: Name = Objektname.** Ein Graph ist aufrufbar, wenn sein Name ein einfacher Name ist (`f`, `g2`, nicht „Funktionsgraph 1“), kein Parameter so heißt und kein zweiter Graph denselben Namen hat. Das passt zur Wertetabelle, die den Namen schon so verwendet. Für Ableitungen heißt der Graph standardmäßig „f'“; zum Aufrufen benennt man ihn um (z. B. `g`).
- **Entscheidung: einsetzen statt aufrufen.** `f(a)` wird beim Einlesen durch den Term von f ersetzt, in dem x durch a ersetzt ist. Bühne und Skript rechnen damit genau dasselbe; im Skript steht der ausgeschriebene Term (kein Zugriff auf das Graph-Objekt nötig, keine Reihenfolgeprobleme).
- **Grenzen:** Stückweise, parametrische, polare und implizite Graphen sowie Integralfunktionen lassen sich (noch) nicht aufrufen; die Meldung sagt das. In Funktionstermen anderer Graphen (`g(x) = f(x − 2)`) geht es bewusst noch nicht: Dafür müssten Ableitung, Nullstellen und alle Graph-Werkzeuge die Verkettung kennen, das wäre ein eigener Schritt.
- **Nebenbei:** Fehler in Termen erscheinen in der Prüfliste jetzt als Satz („Unbekannte Funktion „q“ …“) statt als Code (`unknown_function: q`). Ein leeres Formel-Feld bei einer Zahl zeigt keine Warnung mehr.

## Bühne = Video: Schrift und Achsenmarken (beim Bildvergleich gefunden)
- **Schrift:** Manims `Text` ohne `font=` nimmt Pangos Standardschrift, und die ist eine Serifenschrift (hier Noto Serif, gleiche Breite gemessen; unter Windows/macOS Times). Die Bühne zeichnete Texte, Achsenzahlen und Beschriftungen in der Oberflächenschrift (serifenlos), dadurch waren sie schmaler als im Video und Beschriftungen neben Linien saßen anders. Jetzt nimmt die Bühne die Schrift, die Qt für „serif“ findet. Ein Test vergleicht die Textbreite mit Manim (Abweichung < 2 %).
- **Achsenmarken:** Mit Pfeilspitze lässt Manim die letzte Marke und Zahl weg (dort sitzt die Spitze). Bereiche ohne 0 beginnen bei ihrem ersten Wert. Die Bühne folgt jetzt Manims `get_tick_range` (Test gegen Manim für 16 Fälle).
- **Achsen mit Zahlen (danach behoben):** Manim zentriert die Achsen mitsamt Zahlen (`move_to` nimmt die Box inklusive Beschriftungen). Dadurch lagen Achsen und alles darauf im Video um 0,06 bis 0,25 Einheiten anders als auf der Bühne. Das Modell rechnet die Zahlenkästen jetzt wie Manims `DecimalNumber` (Zeichenbreiten von Pangos Serifenschrift gemessen, Abstand 0,001 × Schriftgröße, negative x-Zahlen ohne Minus zentriert). Mittelpunkt in 8 Fällen gegen Manim geprüft (Abweichung < 0,005). Die Zahlen haben jetzt auch Manims Nachkommastellen (`1.0`, `1.5` bei Schritt 0,5).
- **Offen:** Manim tastet Graphen mit einem Zehntel der Achsenschrittweite ab und glättet dazwischen; bei steilen Stellen (z. B. √x bei 0 mit Schritt 2,5) sieht man im Video einen Knick, die Bühne zeichnet glatt. Eine feinere Abtastung im Skript würde jedes Skript ändern; das habe ich zurückgestellt.

## 3. Wertbeschriftung als eigenes Objekt
- **Was:** Neue Objektart *Wertbeschriftung* (`TOOL_LABEL`) für Tangente und Sekante (Term, Gleichung, Steigung), Punkt am Graphen (Koordinaten, Funktionswert `f(1.50) = 1.12`) und Fläche (Flächeninhalt `A = …`, Integral `∫ f(x) dx = …`). Sie folgt ihrem Werkzeug (mit Parametern live per `always_redraw`), hat aber eigene Animationen: später schreiben, hervorheben, ausblenden. Knopf *Wert als eigene Beschriftung* bei diesen Werkzeugen, auch in der Objektbibliothek (Analysis) bei gewähltem Werkzeug.
- **Damit erfüllt:** dein Wunsch aus dem Nachtrag („Beschriftung erst später einblenden“). Die Vorlage *Tangente wandert am Graphen* schreibt den Term jetzt in einem eigenen Schritt nach der Tangente.
- **Entscheidungen:**
  - Die eigene Beschriftung übernimmt beim Anlegen die Einstellungen der eingebauten (Inhalt, Seite, Nachkommastellen) und schaltet diese ab, alles in einem Rückgängig-Schritt. Die eingebaute Beschriftung bleibt als Option erhalten (ältere Projekte).
  - Flächen werden wie im Skript mit der Simpson-Regel (200 Schritte) berechnet; Bühne und Video zeigen damit dieselben Ziffern. „Flächeninhalt“ zählt Teile unter der Achse positiv, „Integral“ mit Vorzeichen.
  - Position: neben der Linie (wie bisher), oben rechts am Punkt, in der Mitte der Fläche. Weil sie dem Werkzeug folgt, kann man sie nicht ziehen; dafür gibt es *Verschieben nach rechts/oben* (fester Abstand zur automatischen Stelle).
  - Wird die Beschriftung im selben Schritt eingeblendet, in dem sich ihr Parameter ändert, kommt sie automatisch in einen eigenen Schritt (bestehende Regel für Objekte, die Manim aus einem Parameter neu zeichnet).
- **Geprüft:** Text und Mittelpunkt jeder Beschriftung mit Manim 0.19 und 0.22 verglichen (Abweichung < 0,01), alle erlaubten Animationen gerendert, Bildvergleich.
- **Gefunden:** Manims `always_redraw` (`become`) aktualisiert die Form, aber nicht das Attribut `Text.text`; Tests lesen den Text deshalb aus der Bauanleitung. Für Nutzer ohne Bedeutung.
- **Offen:** Riemann-Summen und Markierungen (Nullstellen …) haben noch keine Wertbeschriftung. Die Achsenbeschriftung „y“ stand auf der Bühne etwas höher als im Video (siehe nächster Abschnitt, behoben).

## Bühne = Video: Achsenbeschriftungen x/y
- Manim setzt sie mit `next_to` an die obere rechte Ecke der Achse (Pfeilspitze eingeschlossen), die y-Beschriftung nach rechts und halb nach oben (nicht schräg), und schiebt sie danach ins Bild zurück (`shift_onto_screen`, 0,25 Abstand vom Rand). Die Bühne setzte sie schräg und ohne Zurückschieben; bei Achsen bis an den Bildrand stand „y“ dadurch rund 0,2 Einheiten zu hoch. Jetzt gleich; ein Test vergleicht vier Lagen mit Manim (Abweichung < 0,03).

## Bühne = Video: Gitterlinien der Zahlenebene
- Beim Bildvergleich der nichtlinearen Abbildungen gefunden: Manims `NumberPlane` zeichnet Linien von der Achse aus in beide Richtungen und lässt die äußeren Enden weg (`arange`). Eine Ebene von −7 bis 7 hat also keine Linie bei ±7, eine von −1 bis 4 keine bei −1 und 4. Die Bühne zeichnete sie. Jetzt gleich; Test gegen Manim für 7 Bereiche.

## 4. Komplexe Ebene und nichtlineare Abbildungen
- **Was:** Zwei neue Animationen: *Komplexe Abbildung f(z)* (`ApplyComplexFunction`) und *Punktweise Abbildung* (`ApplyPointwiseFunction`, x′ und y′ in x und y). Die Zahlenebene hat die Option *Zahlen*: keine, reell (`add_coordinates`) oder als komplexe Ebene (`ComplexPlane`). Neue Vorlage *Komplexe Abbildung w = z²* (jetzt 17).
- **Entscheidungen:**
  - Terme in z mit `i` als imaginärer Einheit (`2iz`, `e^(iz)`). Die Bühne rechnet mit `cmath`, das Skript mit NumPy. Funktionen ohne komplexe Entsprechung (floor, sign …) werden gemeldet. Parameter sind in Abbildungen (noch) nicht erlaubt: Manim berechnet das Ziel einmal beim Start der Animation, das ließe sich auf der Bühne nicht ehrlich zeigen.
  - Wo eine Abbildung nicht definiert ist (`1/z` bei 0, `log(0)`), bleibt der Punkt stehen; Bilder weiter als 1000 Einheiten werden auf diesen Kreis zurückgeholt. Skript (`studio_map_point`) und Bühne machen das gleich, sodass Manim nie ungültige Punkte bekommt (sonst Absturz).
  - Vor der Abbildung bekommt das Objekt viele kurze Kurvenstücke (`studio_prepare_map`, wie Manims `prepare_for_nonlinear_transform`), damit Linien sich biegen statt gerade zu bleiben.
  - Nach einer Abbildung kann man das Objekt nicht mehr bewegen, drehen, skalieren oder verwandeln (Prüfung und Bühne sagen das). Die Bühne bildet die Form an ihrem Platz ab; eine spätere Bewegung würde Manim auf die gebogene Form anwenden, die Bühne aber in anderer Reihenfolge. Ein- und Ausblenden, Hervorheben und weitere Abbildungen gehen.
  - Formeln (LaTeX) sind auf der Bühne Bilder und lassen sich nicht biegen; für sie ist die Abbildung gesperrt. Texte gehen.
  - Die komplexe Ebene schreibt i, 2i, −i mit `Text` statt LaTeX (Manims eigene Beschriftung braucht LaTeX für das „i“); Lage wie bei Manim (rechts unterhalb des Punkts). Für 1 steht „i“, nicht „1i“.
- **Gefunden:** `ApplyComplexFunction` definiert einen Bogenweg (Winkel arg f(1)), Manim 0.19 bis 0.22 benutzen ihn aber nie: Die Punkte laufen gerade. Die Bühne macht es ebenso (Test gegen Manims `interpolate`). Manim bildet nur die Ankerpunkte der Bézierkurven exakt ab (die Griffe folgen der Tangente); die Bühne tastet die Umrisse fein ab, beides stimmt im Bild überein.
- **Nebenbei gefunden (eigene Commits):** Gitterlinien der Zahlenebene am Rand (siehe oben).
- **Geprüft:** Bildvergleiche (z², exp, punktweise), Zwischenpositionen gegen Manim, Rendern mit 1/z durch den Ursprung, log, exp, Text, Achsen mit Zahlen und Graph (0.19 und 0.22).

## 5. Kamera dreht dauerhaft (3D)
- **Was:** Neue Kamera-Animation *Kamera dreht dauerhaft* (`begin_ambient_camera_rotation`) mit Geschwindigkeit in °/s und Winkel θ oder φ. Die Drehung beginnt mit ihrem Schritt und läuft durch alle folgenden Schritte und Pausen. Eine weitere Dauerdrehung um denselben Winkel ändert die Geschwindigkeit, 0 °/s hält an. Die Vorlage *3D-Körper mit Kamerafahrt* endet jetzt damit.
- **Entscheidungen:**
  - Als Animation an der Kamera (statt als Szeneneinstellung), damit sie in der Zeitleiste an ihrem Schritt sichtbar ist. Ihre Dauer ist die Mindestdauer des Schritts.
  - Das Skript hält eine laufende Drehung um denselben Winkel vorher an (zwei würden sich in Manim addieren) und am Ende der Szene (sonst drehte sich im Gesamtvideo die nächste Szene weiter).
  - *Kamera schwenken* während einer Dauerdrehung ist gesperrt (Manim würde beides vermischen).
- **Gefunden:** Manims erstes Bild jeder Animation hat dt = 0; pro Schritt dreht sich die Kamera deshalb 1/fps Sekunden kürzer (bei 60 fps 0,3° bei 20 °/s). Die Bühne kennt die Bildrate nicht und rechnet ohne diesen Verlust; der Test hält die Abweichung fest.

## Fuzz-Runde 9 (30 Sitzungen, nach den Abbildungen)
- 28 in Ordnung, 2 Funde:
  - **Echter Fehler:** Ein ungültiger Term in einer komplexen oder punktweisen Abbildung (z. B. `x` statt `z`) ließ die Code-Ansicht mit einer unbehandelten Ausnahme abbrechen. Die Prüfung meldete ihn schon richtig; jetzt meldet auch die Codeerzeugung einen normalen Fehler.
  - **Fehlalarm des Fuzzers:** `Tex(r"\frac{a}{b}")` ohne `$` lehnt LaTeX ab. Die App erkennt das vorher, weil die Bühne jede Formel kompiliert; der Fuzzer prüfte ohne diese Auskunft. Er kompiliert Formeln jetzt selbst vor der Prüfung.

## 6. 3D-Körper bewegen und drehen, Licht wie Manim
- **Was:** Zwei neue Animationen für 3D-Körper: *Im Raum bewegen* (`move_to` an einen Punkt der 3D-Achsen) und *Im Raum drehen* (`Rotate` um die x-, y- oder z-Achse durch die Mitte). Die Bühne schattiert Körper und Flächen jetzt wie Manims `ThreeDCamera`. Die Vorlage *3D-Körper mit Kamerafahrt* dreht den Würfel und hebt den Torus.
- **Licht genau nachgerechnet:** Manim gibt jeder Fläche einen Farbverlauf zwischen ihrer ersten Ecke und einem Punkt nahe der dritten. Die Helligkeit ist 0,5 · (n · l)³ mit festem Licht bei (−7, −9, 10); Schatten zählen halb. Die Normalen berechnet Manim aus benachbarten Bézierpunkten, und die Griffe einer `Surface` bildet es mit einer Linearisierung ab (Faktor 0,01). Das Modell rechnet genau so; Abweichung zu Manim < 0,001 (Würfel exakt). Dabei gefunden und angepasst: Die Ecken der Würfelseiten und der Flächen z = f(x, y) lagen auf der Bühne in anderer Reihenfolge (ohne Licht unsichtbar, mit Licht nicht).
- **Manim-Eigenheit übernommen:** Die Grundfläche eines Kegels hat in Manim `shade_in_3d=False`. Sie wird deshalb nicht schattiert und nach allen schattierten Teilen gezeichnet.
- **Bewegen/Drehen wie Manim:** Ein Körper ist `Anker + Orientierung · Punkt`. `Rotate` dreht um die Mitte des aktuellen Begrenzungsquaders, `move_to` setzt diese Mitte (samt Bézier-Griffen, wie Manims `get_center`). Test: Lage und Licht jeder Fläche nach Drehen, Bewegen, Drehen gleich wie in Manim (Würfel, Kegel, Tetraeder; 0.19 und 0.22).
- **Grenzen:** Die Bühne sortiert ganze Körper nach Tiefe, Manim jede Fläche (bei sich durchdringenden Körpern sichtbar). *Skalieren* eines bewegten Körpers skaliert auf der Bühne um seinen Startpunkt.
- **Nebenbei behoben (aus Punkt 5):** *Kamera dreht dauerhaft* war auch für andere Objekte wählbar und brach dann das Rendern ab; jetzt nur für die Kamera (die Tests „alle Animationen“ der anderen Objektarten haben es gefunden).

## CI wieder grün machen (Schriftart auf dem CI-Rechner)
- Die CI war seit dem Commit „Achsenbeschriftungen“ rot; ich habe das zu spät bemerkt (lokal war alles grün). Ursache: Auf dem CI-Rechner wählt Pango für Manims `Text` „DejaVu Serif“, Qt löst „serif“ dort aber zu einer anderen Schrift auf, und meine Zeichenbreiten für Achsenzahlen stammten von „Noto Serif“.
- Lösung: Bühne und Modell fragen fontconfig (`fc-match serif`) wie Pango. Das Modell hat gemessene Zeichenbreiten für Noto Serif, DejaVu Serif und Liberation Serif; mit DejaVu Serif gegen Manim geprüft (Achsenmitte exakt). Ohne fontconfig (Windows/macOS) gilt Qts eigene Wahl.
- Außerdem war *Kamera dreht dauerhaft* für andere Objekte wählbar (im Commit danach behoben).

## Bühne = Video: Größe und Zeilenabstand von Texten
- Die Bühne richtete die Schriftgröße nach der Höhe der Großbuchstaben aus (an Noto Serif geeicht). Pango richtet sie aber nach dem Geviert (em) aus: Manims `Text` hat ein em von Schriftgröße/72 Einheiten, gemessen gleich für Noto, DejaVu und Liberation Serif und Sans. Bei anderen Schriften war der Text dadurch bis zu 9 % zu breit oder zu schmal (auf dem CI-Rechner mit DejaVu Serif 2,5 %).
- Zeilenabstand: Manim setzt mehrzeilige Texte mit Schriftgröße/96 · (1 + Zeilenabstand), Standard 0,3, ebenfalls für jede Schrift gleich. Die Bühne nahm den Zeilenabstand der Schrift; Zeilen lagen dadurch rund 40 % zu weit auseinander.
- Tests vergleichen Breite und Höhe ein- und mehrzeiliger Texte mit Manim für drei Schriften.
## 7. Zoom-Lupe (ZoomedScene)
- **Was:** Neue Objektart *Lupe (Zoom)* (Bibliothek „Medien“): Rahmen = magnifizierter Bereich (Position des Objekts), Anzeige mit eigener Lage und Größe, Vergrößerung. Animationen: *Einblenden* (die Anzeige springt aus dem Rahmen, wie `get_zoomed_display_pop_out_animation`), *Bewegen*, *Skalieren* (zoomt), *Ausblenden*. Vorlage *Lupe: lokal linear*.
- **Entscheidungen:**
  - Die Szene wird zur `ZoomedScene`; die Lupe ist `self.zoomed_camera.frame`, eingerichtet in `construct` (nicht über `__init__`). So funktioniert sie auch im Gesamtvideo; Manim rechnet die Auflösung der Lupe in jedem Bild aus der Anzeigegröße.
  - Höchstens eine Lupe pro Szene (Manim hat nur eine Zoomkamera), nur in 2D; das Hinzufügen einer zweiten wählt die vorhandene aus.
  - Einblenden und Bewegen der Lupe in einem Schritt lassen sich nicht kombinieren (eigener Code fürs Herausspringen); die Lupe bekommt dann einen eigenen Schritt.
- **Bühne:** Der Rahmen und eine Anzeige, die den gerahmten Teil der Bühne wirklich vergrößert zeigt (gerendert nach jeder Änderung, nicht beim Zeichnen: Qt kann eine Szene nicht in sich selbst zeichnen). Wie bei Manim sieht die Zoomkamera die innere Hälfte ihres eigenen Rahmens, vergrößert als breiter Rand der Anzeige. Bildvergleich: deckungsgleich bis auf Kantenglättung.
- **Hinweis:** Manim vergrößert auch Strichbreiten; bei starker Vergrößerung werden Linien breit. Die Vorlage nimmt deshalb dünne Linien.

## 8a. Bogenbahn (`path_arc`) für Bewegen und Verwandeln
- **Was:** Neuer Parameter *Bogenbahn (°)* bei *Bewegen*, *Verwandeln*, *Ersetzen* und *Aus Kopie verwandeln*. Jeder Punkt läuft auf einem Kreisbogen zum Ziel (Manims `path_along_arc`), positive Winkel gegen den Uhrzeigersinn. Die Bühne zeichnet den Bogen als Bewegungspfad des Schritts. Der Import liest `path_arc`, `ClockwiseTransform` und `CounterclockwiseTransform`.
- **Rechnung:** `path_along_arc` lässt sich als komplexes Gewicht schreiben: p(α) = p + w(α)·(q − p), mit demselben w für alle Punkte. Bewegen bleibt dadurch eine starre Verschiebung entlang des Bogens. Beim Verwandeln mischt die Bühne die beiden Umrisse mit komplexen Gewichten im mitlaufenden Rahmen des Objekts. Ein Test vergleicht jedes Videobild mit der Bühne (Punkt, Mittelpunkt, Breite, Ecke).
- **Entscheidungen:**
  - Bereich ±270°. Bei 360° ist Manims Bogen nicht definiert (Teilung durch tan 180°).
  - *Bewegen* auf einem Bogen zusammen mit *Skalieren*/*Drehen* desselben Objekts im selben Schritt wird als `StudioTransform` erzeugt: Nur die Mitte läuft auf dem Bogen, wie auf der Bühne. Mit `.animate(path_arc=…)` würde Manim auch Skalierung und Drehung „mitdrehen“.
  - *Überblenden* und *Passende Formen verwandeln* bekommen keinen Bogen (sie blenden über bzw. bewegen Teile einzeln).
  - Import: Steht `path_arc` neben `.rotate(…)`, gehört der Bogen zur Drehung (so erzeugt Manim Studio selbst Drehen + Bewegen) und wird nicht zur Bogenbahn.
- **Bühne = Video, dabei gefunden:** Kreise, Ellipsen und Punkte liefen auf der Bühne im Uhrzeigersinn, Rechtecke begannen oben links (Qts `addEllipse`/`addRect`). Manim beginnt Kreise rechts gegen den Uhrzeigersinn und Rechtecke oben rechts. Weil *Verwandeln* die Punkte in dieser Reihenfolge paart, war die Form auf halbem Weg vom Kreis zum Quadrat auf der Bühne zu klein und verdreht (auch ohne Bogen). Außerdem begann *Erzeugen* an einer anderen Stelle als im Video. Jetzt gleich; Bildvergleich mitten in der Verwandlung deckungsgleich.

# Zusammenfassung der Abendschicht (12.10.)

## Fertig (je ein Commit, mit Tests gegen echtes Manim, Doku; gepusht)
1. Mengenformen (Vereinigung, Schnitt, Differenz, symmetrische Differenz), Vorlage Venn-Diagramm
2. Funktionswerte von Graphen in Formeln (`f(a)`)
3. Wertbeschriftung als eigenes Objekt, folgt ihrem Werkzeug
4. Komplexe Ebene und nichtlineare Abbildungen (ApplyComplexFunction/ApplyPointwiseFunction), Vorlage w = z²
5. Kamera dreht dauerhaft (3D)
6. 3D-Körper im Raum bewegen und drehen; Licht wie Manims ThreeDCamera
7. Zoom-Lupe (ZoomedScene), Vorlage „Lupe: lokal linear“
8a. Bewegen und Verwandeln auf einer Bogenbahn (`path_arc`)
- Dazu mehrere Korrekturen „Bühne = Video“ (Schrift wie Pango, Achsenmarken, Achsenbeschriftungen, Gitterlinien, Textgröße und Zeilenabstand, Punktreihenfolge von Kreisen und Rechtecken) und zwei Fuzz-Runden. CI ist für alle Commits bis zur Lupe grün; der Lauf für die Bogenbahn lief beim Schreiben noch (lokal 579 Tests grün, Manim 0.22 und 0.19).

## Nicht fertig (nächste Schritte, in dieser Reihenfolge)
- 8b. Farbverläufe: noch nicht begonnen (nur Manims Verhalten nachgelesen: Verlauf von `c − offset` nach `c + offset`, Richtung UL, dreht beim Drehen mit, in 0.19 und 0.22 gleich).
- 8c. Gestrichelte Varianten aller Formen.
- 9. Graph-Werkzeuge an der Integralfunktion; Import erweitern.
- 10. Weitere Vorlagen/Beispiele, README-GIFs der neuen Funktionen.
- Bekannte Grenzen: 3D sortiert ganze Körper statt Flächen; Skalieren eines bewegten 3D-Körpers; Lupe und 3D nicht im selben Gesamtvideo; keine Parameter in Abbildungstermen.

## Deine Entscheidungen
- Release/Tag/PyPI: nichts veröffentlicht, wartet auf deine Freigabe.
- Bogenbahn zusammen mit Skalieren/Drehen desselben Objekts: ich erzeuge `StudioTransform` (nur die Mitte läuft auf dem Bogen, wie auf der Bühne) statt Manims `.animate(path_arc=…)`, das auch Skalierung/Drehung „mitdreht“. **Entschieden: bleibt so.**

# Session 13.10.

## 8b. Farbverläufe
- **Was:** Formen (Kreis, Quadrat, Rechteck, Ellipse, Dreieck, Vieleck, regelmäßiges Vieleck, Stern, Sektor, Ring) und Linien/Bögen haben die Parameter *Farbverlauf* (keiner/Füllung/Rand/beides), *Zweite Farbe* und *Richtung der zweiten Farbe*. Erzeugt wird `set_fill([a, b])`/`set_stroke([a, b])` und bei Bedarf `set_sheen_direction(…)`, vor dem Drehen des Objekts. Der Import liest das wieder ein.
- **Manim nachgerechnet:** Cairo zeichnet einen linearen Verlauf von `c − offset` nach `c + offset`. Dabei ist `c` die Mitte des Begrenzungsrahmens des *gedrehten* Objekts und `offset = (dx·w/2, dy·h/2)` mit der Glanzrichtung (Standard UL, nicht normiert). Die Richtung dreht `VMobject.rotate` mit (0.19 und 0.22). Die Bühne rechnet die Linie genauso aus ihrer Zeichnung aus. Ein Test vergleicht Anfang und Ende mit `get_gradient_start_and_end_points()` für fünf Formen (gedreht, skaliert), der Bildvergleich ist deckungsgleich.
- **Zustand:** Zweite Farben stehen im Zustand (`fill_color2`/`stroke_color2`). *Farbe ändern* macht das Objekt einfarbig (wie `set_color` mit einer Farbe), unterwegs mischt die Bühne beide Farben zum Ziel wie Manim (eine Farbe wird auf zwei gestreckt). *Verwandeln* mischt die Verläufe.
- **Entscheidungen:** Keine Verläufe für Texte (Manim färbt dort Buchstaben einzeln, eigenes Thema), Pfeile (Spitze ist ein eigenes Teilobjekt mit eigenem Verlauf) und Mengenformen (werden mit `always_redraw` neu gebaut).
- **Grenze:** Während einer Drehung mischt Manim die Glanzrichtung linear (nicht drehend); die Bühne dreht sie mit. Sichtbar nur mitten in einer Drehung eines Objekts mit Verlauf und nur wenig.

## Bühne = Video: Linienenden und Ecken
- Beim Bildvergleich der Farbverläufe gefunden: Die Bühne zeichnete runde Linienenden und Ecken, Manim (Cairo) gerade Enden und spitze Ecken. Die Gehrungsgrenze liegt bei Cairo bei 10 Linienbreiten, gemessen von der Innenecke; bei Qt entspricht das 5, weil Qt von der Linienmitte misst. Gilt so in 0.19 und 0.22 (AUTO = Cairo-Standard). Jetzt gleich, Bildvergleich mit dicken Linien, Stern, Dreieck und Bogen deckungsgleich.

## 8c. Gestrichelte Formen
- **Was:** Kreis, Ellipse, Bogen, Quadrat, Rechteck, Dreieck, n-Eck, Vieleck, Stern und Sektor haben *Gestrichelt (nur Rand)*, *Anzahl Striche* (Manims Standard 15) und *Strichanteil* (0,5). Erzeugt wird `DashedVMobject(Form(…, fill_opacity=0), num_dashes=…, dashed_ratio=…)`. Der Import liest das wieder ein.
- **Manim nachgerechnet:** `DashedVMobject` teilt den Umriss nach Bogenlänge. Geschlossene Umrisse haben gleich viele Lücken wie Striche, offene beginnen und enden mit einem Strich. Das Modell (`model/dashes.py`) schneidet den Umriss in Manims Punktreihenfolge (`paths.local_outline`, neu auch für den Sektor). `move_to` zentriert den Rahmen der *Striche*, die Bühne genauso. Test: Anfang und Ende jedes Strichs von zehn Formen und der Strichlinie (gedreht, skaliert) wie in Manim 0.19 und 0.22, Abweichung < 0,03. Bildvergleich deckungsgleich, auch mit Farbverlauf (in Manim hat jeder Strich seinen eigenen Verlauf, auf der Bühne jetzt auch).
- **Entscheidungen:**
  - Gestrichelte Formen sind nur Rand, ohne Füllung. Ein gefüllter `DashedVMobject` füllt in Manim jeden Strich als Kreissegment, das sieht falsch aus. Wer Füllung will, legt eine zweite Form darunter.
  - Verwandeln (alle Arten) ist für gestrichelte Formen gesperrt: Manim verformt dabei jeden Strich einzeln in die andere Form. Als Pfad und als Teil einer Mengenform gehen sie ebenfalls nicht, weil ein `DashedVMobject` keine eigenen Punkte hat. Validierung und Auswahlfilter sagen das.
  - Gestrichelte Funktionsgraphen und Pfeile vorerst nicht: Werkzeuge am Graphen brauchen den echten Graphen, und Pfeilspitzen behandelt `DashedVMobject` erst ab 0.20 richtig.
- **Nebenbei (Bühne = Video):** Die Strichlinie setzte ihre Striche anders als `DashedLine` (letzter Strich endete vor dem Ende). Der Sektor lief auf der Bühne andersherum als in Manim (Mitte → Bogenende → zurück), deshalb begann *Erzeugen* an der falschen Stelle. Beides jetzt wie Manim.

## 9a. Graph-Werkzeuge an der Integralfunktion
- **Was:** Punkt, Tangente, Sekante, Fläche, Riemann-Summe, Nullstellen/Extrema/Wendepunkte/Schnittpunkte, Beschriftung, Wertetabelle und Wertbeschriftung gehen jetzt auch an F(x) = C + ∫ f(t) dt, auch wenn f Parameter enthält. Ableitung und Integralfunktion *von F* bleiben gesperrt (F hat keinen Term; F′ ist wieder f).
- **Wie:** Das Modell kennt „Werkzeug-Graphen“ (`is_tool_graph`): F rechnet über die numerische Tabelle (jetzt zwischengespeichert), die Steigung von F ist der Integrand f. Extrema von F sind Nullstellen von f mit Vorzeichenwechsel, Wendepunkte von F liegen bei den Extrema von f. Im Skript ist F `C + studio_integral(f, a, x)`; Manims `get_area`/`get_riemann_rectangles` nutzen `underlying_function` des `studio_plot`-Graphen.
- **Test:** F = x³/3 − x zu f = x² − 1: alle Werkzeuge analytisch geprüft; Punkt, Tangente, Riemann-Rechtecke und Extrema wie in Manim (0.19 und 0.22). Bildvergleich deckungsgleich.

## Fuzz-Runde 10 (30 Sitzungen, nach Farbverläufen und Strichen)
- 0 von 30 fehlgeschlagen. Eine Sitzung brauchte sehr lange: Der Fuzzer rendert ohne `-ql` (1080p, 60 fps), und die 3D-Vorlage mit Dauerdrehung zeichnet dann jedes Bild in voller Größe. Kein Fehler, nur langsam.

## 9b. Import erweitert: Graph-Werkzeuge aus Manim-Skripten
- **Was:** Der Skript-Import liest jetzt `ax.plot_derivative_graph(g)`, `ax.plot_antiderivative_graph(g, y_intercept=C)` (Manim integriert ab 0), `ax.get_area(g, x_range, bounded_graph=…)`, `ax.get_riemann_rectangles(…)`, `ax.get_secant_slope_group(x, g, dx)`, `ax.get_graph_label(g, label, x_val, direction)`, Punkte `Dot(ax.i2gp(x, g))` sowie Kurven aus `plot_parametric_curve` und `plot_polar_graph`.
- **Test:** Ein typisches Analysis-Skript wird ohne übersprungene Zeilen eingelesen, ist gültig, erzeugt Code und läuft in Manim 0.19 und 0.22.
- **Grenze:** Nicht gelesen werden u. a. `always_redraw` mit Werkzeugen und `ValueTracker` in Werkzeug-Positionen (Kopplung an Parameter). Solche Zeilen landen wie bisher in der Liste der übersprungenen Zeilen.
