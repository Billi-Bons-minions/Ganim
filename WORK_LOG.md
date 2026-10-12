# Arbeitsprotokoll (Nachtschicht)

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
