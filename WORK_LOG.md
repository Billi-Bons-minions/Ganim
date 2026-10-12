# Arbeitsprotokoll (Nachtschicht)

> **WICHTIG – Push blockiert:** Dieser Rechner hat keine GitHub-Zugangsdaten.
> Es gibt keinen SSH-Schlüssel für GitHub, kein `gh` und keinen Credential-Helper.
> `git push` endet mit „could not read Username“.
> Alles ist lokal auf `main` committet und mit `ganim/main` zusammengeführt.
> Zum Hochladen genügt nach dem Anmelden ein Befehl (Fast-Forward, kein Force nötig):
>
>     cd ~/Documents/manim-gui && git push ganim main
>
> Ohne diesen Push sieht die Cloud-Session den neuen Stand nicht.

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
