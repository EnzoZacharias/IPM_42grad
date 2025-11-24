# Intelligenter Fragebogen - KI-Assistent

KI-gestützter Befragungs-Assistent zur Informationsaufnahme und Prozessdokumentation

## Über das Projekt

Dieser intelligente Fragebogen hilft dabei, Geschäftsprozesse zu dokumentieren, indem er verschiedene Stakeholder (IT, Management, Fachabteilung) strukturiert befragt. Der KI-Assistent:

- stellt automatisch relevante Fragen abhängig von der Rolle der befragten Person
- erkennt fehlende oder unklare Informationen und fragt gezielt nach
- dokumentiert die Antworten strukturiert (z.B. als Prozessbeschreibung)
- kann als Vorstufe zur Automatisierung genutzt werden

## Installation

1. Virtuelle Umgebung aktivieren:
```bash
.venv\Scripts\Activate.ps1  # PowerShell
# oder
.venv\Scripts\activate.bat  # CMD
```

2. Dependencies installieren (falls noch nicht geschehen):
```bash
pip install -r requirements.txt
```

3. `.env` Datei erstellen mit Mistral API-Key:
```
MISTRAL_API_KEY=your_api_key_here
```

## Verwendung

### Chat-Interface (Empfohlen)

Starte den interaktiven Chat direkt:

```bash
python chat.py
```

Oder doppelklicke auf `start_chat.bat` (Windows)

Der Chat-Assistent führt dich Schritt für Schritt durch das Interview:
- Beantworte Frage für Frage
- Gib `status` ein, um den aktuellen Stand zu sehen
- Gib `dokument` ein, um eine Zwischendokumentation zu generieren
- Gib `exit` ein, um das Interview zu beenden

### REST-API (Optional)

Alternativ kannst du die REST-API verwenden:

```bash
uvicorn app.main:app --reload
```

Die API läuft dann auf `http://127.0.0.1:8000`

Beim Start wird automatisch eine Session erstellt und die erste Frage angezeigt.

API-Endpoints:
- `POST /start` - Neue Session starten
- `POST /answer` - Antwort senden
- `GET /status/{session_id}` - Status abrufen
- `POST /document` - Dokumentation generieren

## Projektstruktur

```
interview-orchestrator/
├── chat.py                 # Chat-Interface (Haupteinstieg)
├── start_chat.bat          # Windows-Starter
├── app/
│   ├── main.py            # FastAPI REST-API
│   ├── models.py          # Datenmodelle
│   └── llm/
│       └── mistral_client.py
├── interview/
│   ├── engine.py          # Interview-Logik
│   ├── repo.py            # Fragen-Repository
│   └── role_classifier.py # Rollen-Klassifikation
├── doc/
│   └── generator.py       # Dokumenten-Generator
└── config/
    └── questions.json     # Fragenkatalog
```

## Features

- ✅ Rollenbasierte Fragestellung (IT, Management, Fachabteilung)
- ✅ Intelligente Rollenerkennung via KI
- ✅ Interaktives Chat-Interface
- ✅ Automatische Dokumentgenerierung
- ✅ REST-API für Integration
- ✅ Speicherung der Dokumentation

## Entwickelt für

42grad GmbH im Rahmen des Projekts "Intelligenter Fragebogen – KI-Assistent zur Informationsaufnahme und Prozessdokumentation"
