# Interview-Orchestrator Backend
## Technische Präsentation

---

# Folie 1: Systemarchitektur

## Zwei-Phasen-Interview-Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 1: INTAKE                          │
│         9 neutrale Klassifizierungsfragen                   │
│              (ohne RAG für Neutralität)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               ROLLENKLASSIFIZIERUNG                         │
│     Gewichteter Scoring-Algorithmus (70% Schwelle)          │
│         → Fachabteilung | IT | Management                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 PHASE 2: ROLE-SPECIFIC                      │
│      Schema-basierte Fragen mit selektivem RAG              │
│           (nur für technische Themen)                       │
└─────────────────────────────────────────────────────────────┘
```

### Kernkomponenten
- **Flask Web Server** (Python) - REST API
- **Mistral LLM** - Fragengeneration & Analyse
- **RAG-System** - Kontextanreicherung
- **JSON Session Store** - Persistenz

---

# Folie 2: LLM-Integration & Prompt Engineering

## Unified Mistral Client

| Feature | Beschreibung |
|---------|--------------|
| **Dual-Mode** | Lokales Ollama ODER Cloud API |
| **Auto-Detection** | Automatische Erkennung verfügbarer Backends |
| **JSON-Modus** | Strukturierte Ausgaben für Klassifizierung |
| **Fallback** | Graceful Degradation bei Fehlern |

## Prompt Engineering Strategie

### Intake-Phase (Statisches Schema)
```python
INTAKE_QUESTIONS_SCHEMA = {
    "intake_1": {
        "question": "Welche Rolle haben Sie im Unternehmen?",
        "type": "yes_no_discriminator",  # Höchste Gewichtung
        "weight": 0.4
    },
    # ... 9 Fragen total
}
```

### Role-Phase (Dynamische Generation)
- **Kontext-Injection** via RAG (selektiv)
- **Schema-gesteuerte** Fragenkategorien
- **Adaptive Nachfragen** bei unvollständigen Antworten

---

# Folie 3: RAG-System (Retrieval-Augmented Generation)

## Technologie-Stack

| Komponente | Technologie |
|------------|-------------|
| **Vector Store** | FAISS (Facebook AI) |
| **Embeddings** | sentence-transformers/all-MiniLM-L6-v2 |
| **Framework** | LangChain |
| **Chunking** | 1000 Zeichen, 200 Overlap |

## Selektive RAG-Aktivierung

```python
TECHNICAL_KEYWORDS = [
    "system", "prozess", "schnittstelle", "daten",
    "workflow", "integration", "technisch"
]

def should_use_rag(question_category: str) -> bool:
    # RAG nur für technische Fragen aktivieren
    # Vermeidet Bias bei allgemeinen Fragen
```

## Dokument-Pipeline
1. **Upload** → PDF/TXT Extraktion
2. **Chunking** → Semantische Segmente
3. **Embedding** → Vektorrepräsentation
4. **Retrieval** → Top-k relevante Chunks (k=3)
5. **Injection** → Kontext in LLM-Prompt

---

# Folie 4: Rollenklassifizierung

## Gewichteter Scoring-Algorithmus

```
┌────────────────────────────────────────────────────────┐
│  KLASSIFIZIERUNGS-GEWICHTE                             │
├────────────────────────────────────────────────────────┤
│  Yes/No Discriminators    ████████████████████  40%    │
│  Rollenbegriffe           ████████████████      30%    │
│  Aufgabenbeschreibungen   ██████████            15%    │
│  Problemstellungen        ████████               10%   │
│  Metriken/KPIs            ████                    5%   │
└────────────────────────────────────────────────────────┘
```

## Entscheidungslogik

```python
confidence_threshold = 0.70  # 70%

if max_score >= confidence_threshold:
    return classified_role  # Direkte Zuweisung
else:
    if clarification_count < 3:
        return generate_clarifying_question()
    else:
        return default_role  # Fallback: "fach"
```

## Drei Rollen-Schemas
- **Fachabteilung** → Prozess- & Geschäftsfragen
- **IT** → Technische & Integrationsfragen  
- **Management** → Strategie- & Entscheidungsfragen

---

# Folie 5: Session Management & API

## Thread-Safe Session Store

```python
class SessionStore:
    _lock = threading.Lock()  # Thread-Sicherheit
    
    def save_session(self, session_id, data):
        # Auto-Save nach jeder Antwort
        # JSON-Persistenz in /sessions/
```

## REST API Endpoints

| Endpoint | Methode | Funktion |
|----------|---------|----------|
| `/api/session/new` | POST | Neue Session erstellen |
| `/api/session/{id}/answer` | POST | Antwort verarbeiten |
| `/api/session/{id}/status` | GET | Fortschritt abrufen |
| `/api/session/{id}/export` | GET | PDF-Export |
| `/api/documents/upload` | POST | RAG-Dokument hochladen |

## Fallback-Mechanismen

| Szenario | Fallback-Strategie |
|----------|---------------------|
| LLM nicht erreichbar | Statische Fragen aus Schema |
| Klassifizierung unsicher | Default-Rolle "Fachabteilung" |
| RAG-Fehler | Interview ohne Kontext fortsetzen |
| Session-Korruption | Neuer Session-Start |

---

# Folie 6: PDF-Dokumentgenerierung

## Architektur der Ausgabegenerierung

```
┌─────────────────────────────────────────────────────────────┐
│              INTERVIEW-DATEN SAMMELN                        │
│     • Intake-Antworten (9 Fragen)                          │
│     • Rollenspezifische Antworten (Schema-basiert)         │
│     • Schema-Fields mit Metadaten                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM-ANALYSE & AUFBEREITUNG                     │
│     Mistral analysiert, interpretiert & strukturiert       │
│     → Professionelle Aussagen statt Zitate                 │
│     → JSON-Output mit 25+ strukturierten Feldern           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              PDF-RENDERING (ReportLab)                      │
│     • Titelseite mit Metadaten                             │
│     • 5 strukturierte Abschnitte                           │
│     • Anhang mit Rohdaten                                  │
└─────────────────────────────────────────────────────────────┘
```

## LLM-Prompt für Dokumentanalyse

| Aspekt | Beschreibung |
|--------|--------------|
| **Analyse-Tiefe** | Nicht nur extrahieren, sondern INTERPRETIEREN |
| **Stil** | Professionelle Aussagen, keine "der Befragte sagte..." |
| **Kontext** | Implikationen und Zusammenhänge erkennen |
| **Detailgrad** | Min. 2-3 vollständige Sätze pro Punkt |

## PDF-Struktur (5 Abschnitte)

| Abschnitt | Inhalt |
|-----------|--------|
| **1. Executive Summary** | Management-Zusammenfassung, Ist-Situation, Rollen, Systeme |
| **2. Problemanalyse** | Hauptprobleme, Fehlerquellen, Risiken, offene Punkte |
| **3. Prozessablauf** | Schritte, Eingaben, Ausgaben, Entscheidungspunkte, Varianten |
| **4. Potenziale** | Automatisierung, Quick Wins, strategische Maßnahmen |
| **5. Ergänzungen** | Compliance, Kennzahlen, Fazit |
| **Anhang** | Vollständige Interview-Rohdaten |

## LLM-Output Schema (25+ Felder)

```json
{
  "prozessname": "Präziser Name",
  "executive_summary": "8-12 Sätze Management-Summary",
  "ist_situation": "6-10 Sätze aktuelle Situation",
  "beteiligte_rollen": ["Rolle + Beschreibung (2-3 Sätze)"],
  "genutzte_systeme": ["System + Stärken/Limitationen"],
  "hauptprobleme": ["Problem + Ursachen + Auswirkungen (3-4 Sätze)"],
  "prozessschritte": ["Schritt + Verantwortlicher + Ergebnis"],
  "automatisierungspotenziale": ["Was + Aufwand + Nutzen"],
  "quick_wins": ["Schnelle Verbesserung (2-3 Sätze)"],
  "verbesserungsempfehlungen": ["Empfehlung + Begründung"],
  "fazit": "5-8 Sätze Gesamtbewertung"
  // ... weitere Felder
}
```

## Fallback-Mechanismus

```python
def _fallback_processing(interviews):
    """Keyword-basierte Extraktion wenn LLM fehlt"""
    
    # Keyword-Listen für automatische Kategorisierung
    system_keywords = ['system', 'software', 'excel', 'sap', ...]
    problem_keywords = ['problem', 'fehler', 'manuell', ...]
    goal_keywords = ['ziel', 'verbessern', 'optimieren', ...]
    
    # Sätze extrahieren die Keywords enthalten
    systems = extract_sentences(text, system_keywords)
    problems = extract_sentences(text, problem_keywords)
    # ...
```

---

# Anhang: Technologie-Übersicht

## Dependencies

```
Flask==3.1.1          # Web Framework
langchain==0.3.25     # RAG Framework
langchain-huggingface # Embeddings
faiss-cpu==1.11.0     # Vector Store
mistralai==1.8.1      # Cloud API
requests              # Ollama HTTP
reportlab             # PDF-Generierung
```

## Konfigurationsparameter

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `CHUNK_SIZE` | 1000 | RAG Chunk-Größe |
| `CHUNK_OVERLAP` | 200 | Überlappung |
| `TOP_K_RESULTS` | 3 | Relevante Chunks |
| `CONFIDENCE_THRESHOLD` | 0.70 | Klassifizierung |
| `MAX_CLARIFICATIONS` | 3 | Nachfragen |

