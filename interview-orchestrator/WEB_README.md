# Interview-Orchestrator - Web-Interface

## Übersicht

Diese leichtgewichtige Flask-Webanwendung bietet eine benutzerfreundliche Web-Oberfläche für den Interview-Orchestrator.

## Features

### ✅ Implementiert (Konzept-Version)

- **💬 Chat-Interface**: Interaktive Fragenbeantwortung mit klarer Darstellung
- **📊 Status-Anzeige**: 
  - Aktuelle Phase (Einstiegsfragen / Rollenspezifische Fragen)
  - Zugewiesene Rolle (Undefiniert → Fachbereich / Management / IT)
  - Anzahl beantworteter Fragen
  - Anzahl hochgeladener Dateien
- **🔄 Reset-Funktion**: Neustart des Interviews mit Bestätigungsdialog
- **📁 Dokument-Upload**: 
  - Drag & Drop Support
  - Mehrfachauswahl
  - Anzeige hochgeladener Dateien mit Größe
  - (Verarbeitung folgt in späteren Versionen)
- **🎨 Modernes UI**: Responsive Design mit Gradient-Header

### 🚧 Für spätere Versionen geplant

- Echtes LLM-Streaming für Antworten
- Dokumentenverarbeitung und -analyse
- Export der Dokumentation
- Erweiterte Visualisierungen
- Multi-User Support

## Installation

1. Dependencies installieren:
```bash
pip install -r requirements.txt
```

2. Umgebungsvariablen konfigurieren (`.env` Datei):
```
MISTRAL_API_KEY=your_api_key_here
FLASK_SECRET_KEY=your_secret_key_here
```

## Start

### Option 1: Batch-Datei (Windows)
```bash
start_web.bat
```

### Option 2: Direkt mit Python
```bash
python web_app.py
```

Der Server startet auf: **http://localhost:5000**

## Projektstruktur

```
interview-orchestrator/
├── web_app.py              # Flask-Hauptanwendung
├── start_web.bat           # Windows-Startskript
├── templates/              # HTML-Templates
│   ├── base.html          # Basis-Template
│   └── index.html         # Hauptseite
├── static/                # Statische Dateien
│   ├── css/
│   │   └── style.css     # Styling
│   └── js/
│       └── app.js        # Frontend-Logik
├── uploads/               # Upload-Verzeichnis (auto-generiert)
└── ...                    # Bestehende Module
```

## API-Endpoints

### `POST /api/start`
Startet ein neues Interview und gibt die erste Frage zurück.

**Request:**
```json
{
  "session_id": "session_xyz"
}
```

**Response:**
```json
{
  "success": true,
  "question": {...},
  "status": {...}
}
```

### `POST /api/answer`
Sendet eine Antwort und erhält die nächste Frage.

**Request:**
```json
{
  "session_id": "session_xyz",
  "question_id": "q1",
  "answer": "Antworttext"
}
```

**Response:**
```json
{
  "success": true,
  "question": {...},
  "status": {...},
  "completed": false
}
```

### `POST /api/reset`
Setzt das Interview zurück.

### `GET /api/status`
Gibt den aktuellen Status zurück.

### `POST /api/upload`
Lädt eine Datei hoch (ohne Verarbeitung).

**Form Data:**
- `file`: Die hochzuladende Datei
- `session_id`: Session-ID

### `GET /api/files`
Gibt die Liste hochgeladener Dateien zurück.

## Verwendung

1. **Interview starten**: Seite öffnen, automatisch wird die erste Frage gestellt
2. **Fragen beantworten**: Antwort eingeben und "Senden" klicken oder Enter drücken
3. **Status beobachten**: Linkes Panel zeigt aktuelle Phase und Rolle
4. **Dateien hochladen**: Rechtes Panel für Dokument-Upload (Drag & Drop oder Auswahl)
5. **Neu starten**: Bei Bedarf über "🔄 Neu starten" Button

## Technologie-Stack

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Styling**: Custom CSS mit Gradient-Design
- **AI/LLM**: Mistral AI (über bestehende Integration)

## Hinweise

- Dies ist eine **Konzept-Version** - die vollständige Implementierung folgt
- Streaming ist vorbereitet, aber noch nicht aktiv implementiert
- Dokument-Upload funktioniert, aber Verarbeitung ist noch nicht implementiert
- Sessions werden im Speicher gehalten (nicht persistent)

## Nächste Schritte

1. Echtes LLM-Streaming implementieren
2. Dokumentenverarbeitung integrieren
3. Persistente Session-Speicherung
4. Export-Funktionalität
5. Erweiterte Validierung
6. Unit Tests

---

**Version**: 1.0.0 (Konzept)  
**Status**: Proof of Concept
