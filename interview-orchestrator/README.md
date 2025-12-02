# Intelligenter Fragebogen - KI-Assistent

KI-gestützter Befragungs-Assistent zur Informationsaufnahme und Prozessdokumentation mit RAG-System

## Über das Projekt

Dieser intelligente Fragebogen hilft dabei, Geschäftsprozesse zu dokumentieren, indem er verschiedene Stakeholder (IT, Management, Fachabteilung) strukturiert befragt. Der KI-Assistent:

- stellt automatisch relevante Fragen abhängig von der Rolle der befragten Person
- erkennt fehlende oder unklare Informationen und fragt gezielt nach
- dokumentiert die Antworten strukturiert (z.B. als Prozessbeschreibung)
- kann als Vorstufe zur Automatisierung genutzt werden
- **NEU: Nutzt hochgeladene Dokumente (PDF/TXT) als Kontext für bessere Fragen (RAG-System)**

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

3. **Lokales LLM einrichten (Ollama mit Mistral-Small)**:

   a) Ollama installieren: https://ollama.ai/download
   
   b) Ollama starten:
   ```bash
   ollama serve
   ```
   
   c) Mistral-Small Modell herunterladen:
   ```bash
   ollama pull mistral-small
   ```
   
   d) `.env` Datei erstellen/anpassen:
   ```
   LOCAL_LLM_URL=http://localhost:11434
   LOCAL_LLM_MODEL=mistral-small
   ```

   **Alternative Server:**
   - LM Studio: `LOCAL_LLM_URL=http://localhost:1234`
   - vLLM: `LOCAL_LLM_URL=http://localhost:8000`

## Verwendung

### Web-Interface (Empfohlen)

Starte die Web-Anwendung:

```bash
python web_app.py
```

Oder doppelklicke auf `start_web.bat` (Windows)

Die Web-Anwendung läuft dann auf `http://localhost:5000`

#### Features der Web-Anwendung:
- **Dokument-Upload**: Lade PDF- oder TXT-Dateien hoch
- **RAG-Integration**: Das System nutzt die hochgeladenen Dokumente automatisch als Kontext
- **Intelligente Fragen**: Fragen werden auf Basis der Dokumente angepasst
- **Session-Management**: Mehrere gleichzeitige Interviews möglich
- **Live-Status**: Echtzeit-Anzeige des Interview-Fortschritts

### Chat-Interface (Alternativ)

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

## RAG-System (Retrieval-Augmented Generation)

Das Interview-Tool enthält nun ein **RAG-System**, das hochgeladene Dokumente analysiert und als Kontext für die Fragengenerierung nutzt.

### Funktionsweise

1. **Dokumente hochladen**: Lade PDF- oder TXT-Dateien über die Web-Oberfläche hoch
2. **Automatische Indexierung**: Das System erstellt automatisch Embeddings und einen Vektorindex
3. **Kontextbasierte Fragen**: Bei jeder Frage wird relevanter Kontext aus den Dokumenten abgerufen
4. **Angepasste Fragen**: Das LLM generiert Fragen, die auf die spezifische Organisation zugeschnitten sind

### Unterstützte Dateiformate

- **PDF**: Automatische Textextraktion aus PDF-Dokumenten
- **TXT**: Plain-Text-Dateien

### Technische Details

- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Vektorstore**: FAISS für schnelle semantische Suche
- **Chunking**: Intelligente Textaufteilung mit Überlappung
- **Retrieval**: Top-3 relevanteste Dokumente pro Frage

### Beispiel-Workflow

```
1. Starte Web-App → http://localhost:5000
2. Lade Prozessdokumente hoch (z.B. "Prozessbeschreibung.pdf")
3. Starte Interview → System initialisiert RAG
4. Beantworte Fragen → Fragen basieren auf deinen Dokumenten
5. Generiere Dokumentation → Vollständige Prozessdokumentation
```

## Projektstruktur

```
interview-orchestrator/
├── chat.py                 # Chat-Interface
├── web_app.py              # Web-Interface (Flask)
├── start_chat.bat          # Windows-Starter für Chat
├── start_web.bat           # Windows-Starter für Web
├── app/
│   ├── main.py            # FastAPI REST-API
│   ├── models.py          # Datenmodelle
│   └── llm/
│       └── mistral_client.py
├── interview/
│   ├── engine.py          # Interview-Logik (mit RAG-Integration)
│   ├── repo.py            # Fragen-Repository
│   ├── question_generator.py  # Dynamische Fragengenerierung (RAG-aware)
│   └── role_classifier.py # Rollen-Klassifikation
├── rag/                    # NEU: RAG-System
│   ├── __init__.py
│   └── rag_system.py      # Dokumentenverarbeitung und Retrieval
├── doc/
│   └── generator.py       # Dokumenten-Generator
├── config/
│   └── questions.json     # Fragenkatalog (Fallback)
└── uploads/               # Hochgeladene Dokumente
```

## Features

- ✅ Rollenbasierte Fragestellung (IT, Management, Fachabteilung)
- ✅ Intelligente Rollenerkennung via KI
- ✅ **RAG-System für kontextbasierte Fragen**
- ✅ **PDF/TXT Dokument-Upload und Analyse**
- ✅ Web-Interface mit Echtzeit-Updates
- ✅ Interaktives Chat-Interface
- ✅ Automatische Dokumentgenerierung
- ✅ REST-API für Integration
- ✅ Session-Management für mehrere Interviews

## Entwickelt für

42grad GmbH im Rahmen des Projekts "Intelligenter Fragebogen – KI-Assistent zur Informationsaufnahme und Prozessdokumentation"
