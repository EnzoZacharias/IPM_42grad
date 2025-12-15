# Technische Dokumentation: Backend-Implementierung des Interview-Orchestrators

**Projekt:** IPM_42grad - Intelligenter Prozess-Management Fragebogen  
**Version:** 1.0  
**Datum:** Dezember 2024  
**Verantwortungsbereich:** Backend-Entwicklung

---

## Inhaltsverzeichnis

1. [Backend-Architektur](#1-backend-architektur)
2. [LLM-Integration und Mistral-Client](#2-llm-integration-und-mistral-client)
3. [Prompt-Engineering](#3-prompt-engineering)
4. [RAG-System Implementation](#4-rag-system-implementation)
5. [Rollenklassifikations-Algorithmus](#5-rollenklassifikations-algorithmus)
6. [Interview-Engine und Phasensteuerung](#6-interview-engine-und-phasensteuerung)
7. [Schema-Manager und Fortschrittsverfolgung](#7-schema-manager-und-fortschrittsverfolgung)
8. [Session-Management und Persistenz](#8-session-management-und-persistenz)
9. [REST-API Implementation](#9-rest-api-implementation)
10. [Fallback-Mechanismen und Fehlerbehandlung](#10-fallback-mechanismen-und-fehlerbehandlung)

---

## 1. Backend-Architektur

### 1.1 Systemübersicht

Das Backend besteht aus mehreren lose gekoppelten Modulen, die über definierte Schnittstellen kommunizieren:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Flask Web-Server (web_app.py)                   │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │  API Endpoints │  │  Session       │  │  File Upload           │ │
│  │  (/api/*)      │  │  Management    │  │  Handler               │ │
│  └────────────────┘  └────────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Interview-Orchestrator                          │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │  InterviewEngine │  │  QuestionGenerator│  │  RoleClassifier   │  │
│  │  (engine.py)     │  │  (question_gen.py)│  │  (role_class.py)  │  │
│  └──────────────────┘  └──────────────────┘  └───────────────────┘  │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │  SchemaManager   │  │  SessionStore    │  │  DocGenerator     │  │
│  │  (role_schema.py)│  │  (session_store) │  │  (generator.py)   │  │
│  └──────────────────┘  └──────────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌───────────────────────────┐       ┌───────────────────────────────┐
│       RAG-System          │       │       LLM-Backend             │
│  ┌─────────────────────┐  │       │  ┌──────────────────────────┐ │
│  │  Document Loader    │  │       │  │  MistralClient           │ │
│  │  (PDF/TXT)          │  │       │  │  - Local (Ollama)        │ │
│  ├─────────────────────┤  │       │  │  - Cloud (Mistral API)   │ │
│  │  Text Splitter      │  │       │  └──────────────────────────┘ │
│  │  (Chunking)         │  │       │                               │
│  ├─────────────────────┤  │       │  Modell: mistral-small        │
│  │  HuggingFace        │  │       │  Temperatur: 0.2-0.7          │
│  │  Embeddings         │  │       │  JSON-Mode: aktiviert         │
│  ├─────────────────────┤  │       └───────────────────────────────┘
│  │  FAISS Vector Store │  │
│  │  (Semantic Search)  │  │
│  └─────────────────────┘  │
└───────────────────────────┘
```

### 1.2 Modulstruktur

```
interview-orchestrator/
├── web_app.py                 # Flask Web-Server (1332 Zeilen)
├── chat.py                    # CLI-Interface (Alternative)
│
├── app/
│   ├── main.py               # FastAPI REST-API (Alternative)
│   ├── models.py             # Datenmodelle
│   └── llm/
│       └── mistral_client.py # LLM-Anbindung (550 Zeilen)
│
├── interview/
│   ├── engine.py             # Kern-Interview-Logik (657 Zeilen)
│   ├── question_generator.py # Dynamische Fragengenerierung (1029 Zeilen)
│   ├── role_classifier.py    # KI-Rollenklassifikation (228 Zeilen)
│   ├── role_schema_manager.py# Schema-Verwaltung (441 Zeilen)
│   ├── repo.py               # Fragen-Repository
│   └── session_store.py      # Session-Persistenz
│
├── rag/
│   └── rag_system.py         # RAG-Implementation (441 Zeilen)
│
├── doc/
│   ├── generator.py          # Dokumentengenerierung
│   └── pdf_generator.py      # PDF-Export
│
├── config/
│   ├── questions.json        # Basis-Fragenkatalog
│   ├── role_schema_fach.json # Fachabteilungs-Schema
│   ├── role_schema_it.json   # IT-Schema
│   └── role_schema_management.json # Management-Schema
│
└── uploads/                   # RAG-Dokumente (von Datengruppe bereitgestellt)
```

### 1.3 Besonderheit: Zwei-Phasen-Interview

Eine zentrale Architekturentscheidung war die Aufteilung des Interviews in zwei Phasen:

```python
PHASE_INTAKE = "intake"       # Phase 0: 9 Einstiegsfragen zur Rollenklassifikation
PHASE_ROLE = "role_specific"  # Phase 1: Rollenspezifische Fragen nach Schema
```

**Technische Begründung:**
- **Phase 0 (Intake):** Generiert Fragen dynamisch mit LLM, um die Rolle zu ermitteln. Diese Fragen werden bewusst OHNE RAG-Kontext generiert, um neutrale, nicht-suggestive Fragen zu gewährleisten.
- **Phase 1 (Role-Specific):** Nutzt die JSON-Schemas der Datengruppe und optional RAG-Kontext für branchenspezifische Details.

---

## 2. LLM-Integration und Mistral-Client

### 2.1 Unified Client Architektur

Eine zentrale Herausforderung war die Unterstützung sowohl lokaler LLMs (Ollama) als auch der Cloud-API (Mistral). Die Lösung ist ein **Unified Client**, der beide Backends transparent abstrahiert:

```python
class MistralClient:
    """
    Unified Client für Mistral LLM - unterstützt lokales Modell UND Mistral-API.
    """
    
    def __init__(self, base_url=None, model=None, api_key=None, backend=BACKEND_LOCAL):
        self._backend = backend
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY", "")
        
        # Lokale Server-Konfiguration
        self._local_base_url = base_url or os.getenv("LOCAL_LLM_URL", "http://localhost:11434")
        self._local_model = model or os.getenv("LOCAL_LLM_MODEL", "mistral-small")
        
        # Mistral-API-Konfiguration
        self._mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        self._mistral_model = os.getenv("MISTRAL_API_MODEL", "mistral-small-latest")
        
        # Erkenne Server-Typ für lokales Backend
        self._is_ollama = "11434" in self._local_base_url
        
        # API-Endpoint basierend auf Server-Typ
        if self._is_ollama:
            self._local_chat_endpoint = f"{self._local_base_url}/api/chat"
        else:
            self._local_chat_endpoint = f"{self._local_base_url}/v1/chat/completions"
```

### 2.2 Automatische Backend-Erkennung

Bei Session-Start wird automatisch das verfügbare Backend erkannt:

```python
def get_or_create_session(session_id, load_saved: bool = True):
    # Prüfe zuerst ob lokales Ollama verfügbar ist
    temp_client = MistralClient(backend=BACKEND_LOCAL)
    if temp_client.is_local_available():
        logger.info("🏠 Lokales Ollama Backend verfügbar")
        llm_client = temp_client
    else:
        mistral_api_key = os.getenv("MISTRAL_API_KEY", "")
        if mistral_api_key:
            logger.info("🔑 Verwende Mistral API Backend")
            llm_client = MistralClient(backend=BACKEND_MISTRAL_API, api_key=mistral_api_key)
        else:
            logger.warning("⚠️ Weder Ollama noch Mistral API verfügbar")
            llm_client = temp_client  # Wird fehlschlagen, aber graceful
```

**Vorteil:** Das System kann sowohl auf lokalen Entwicklungsrechnern mit Ollama als auch in Cloud-Umgebungen mit API-Key betrieben werden, ohne Code-Änderungen.

### 2.3 JSON-Mode für strukturierte Ausgaben

Eine kritische Funktion ist der **JSON-Mode**, der garantiert, dass das LLM maschinenlesbare Antworten liefert:

```python
def complete(self, messages, temperature=0.2, max_tokens=None, json_mode=None):
    """
    json_mode: {"type": "json_object"} für strukturierte Ausgaben
    """
    if self._is_ollama:
        payload = {
            "model": self._local_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        if json_mode:
            payload["format"] = "json"  # Ollama-spezifisch
    else:
        # OpenAI-kompatible API
        payload["response_format"] = json_mode
```

### 2.4 Temperatur-Strategie

Unterschiedliche Aufgaben erfordern unterschiedliche Kreativitätsstufen:

| Aufgabe | Temperatur | Begründung |
|---------|------------|------------|
| JSON-Generierung (Fragen) | 0.2 | Deterministische, konsistente Struktur |
| Rollenklassifikation | 0.2 | Reproduzierbare Klassifikation |
| Fragen-Formulierung | 0.7 | Natürliche, variierende Formulierungen |
| Dokumentengenerierung | 0.3 | Balance zwischen Kreativität und Konsistenz |

---

## 3. Prompt-Engineering

### 3.1 System-Prompt für Einstiegsfragen

Der komplexeste Prompt ist der für die dynamische Fragengenerierung. Er muss mehrere Anforderungen gleichzeitig erfüllen:

```python
system_prompt = {
    "role": "system",
    "content": f"""Du bist ein Experte für Prozessanalyse und Organisationspsychologie.
    Deine Aufgabe ist es, 9 strukturierte Einstiegsfragen zu erstellen, die dabei helfen, 
    die Rolle einer Person zu identifizieren.

    **WICHTIG: Die Fragen basieren auf einer wissenschaftlichen Ausarbeitung zur Rollendefinition!**

    Die drei Rollen sind:

    **IT-Rolle** (Technische Verantwortliche):
    - Aufgaben: Systemadministration, Schnittstellenbetreuung, Softwareentwicklung
    - Probleme: Systemausfälle, fehlende Schnittstellen
    - Erfolgsmessung: Systemstabilität, Anzahl automatisierter Prozesse

    **Fach-Rolle** (Fachabteilung/Sachbearbeiter):
    - Aufgaben: Bearbeitung von Bestellungen, Dokumentenprüfung, operative Prozessarbeit
    - Probleme: Fehler in Dokumenten, Rückfragen, hohe Arbeitslast
    - Erfolgsmessung: Bearbeitungszeit, Fehlerquote
    - Trifft hauptsächlich operative Entscheidungen

    **Management-Rolle** (Führungskräfte):
    - Aufgaben: Strategische Planung, Projektleitung, Budgetverantwortung
    - Probleme: Verzögerungen, fehlende Transparenz
    - Erfolgsmessung: Kostenreduktion, Prozessdurchlaufzeit
    - Leitet Projekte oder Teams

    **Die 9 Fragen MÜSSEN in dieser Reihenfolge abdecken:**
    1. **Rolle/Funktion** - OFFEN (kein Multiple Choice!)
    2. **Aufgaben/Verantwortungsbereich** - Offen
    3. **Ziele im Prozess** - Offen
    4. **Probleme/Herausforderungen** - Offen
    5. **Zusammenarbeit** - Offen
    6. **Erfolgsmessung** - Offen
    7. **Operative Entscheidungen** - Ja/Nein Frage
    8. **Technische Verantwortung** - Ja/Nein Frage
    9. **Projektleitung/Teams** - Ja/Nein Frage

    Antworte AUSSCHLIESSLICH im folgenden JSON-Format:
    {{
      "questions": [
        {{
          "id": "role_function",
          "text": "Die formulierte Frage",
          "type": "text|choice",
          "options": ["Option1", "Option2"],
          "required": true
        }}
      ]
    }}
    """
}
```

### 3.2 Dynamische Einzelfragen-Generierung

Für kontextsensitive Fragen wird jede Frage einzeln generiert, basierend auf dem bisherigen Gesprächsverlauf:

```python
def generate_single_intake_question(self, question_index, answers, previous_questions, document_summary=""):
    schema = self.intake_question_schema[question_index]
    
    # Kontext aus vorherigen Antworten aufbauen
    context_parts = []
    for i, q in enumerate(previous_questions):
        q_id = q.get("id", "")
        answer = answers.get(q_id, "")
        if answer:
            context_parts.append(f"Frage {i+1} ({q.get('topic', '')}): {q.get('text', '')}\nAntwort: {answer}")
    
    previous_context = "\n\n".join(context_parts) if context_parts else "Noch keine Antworten."
    
    system_prompt = {
        "role": "system",
        "content": f"""Du führst ein Interview zur Prozessdokumentation.

        Frage Nr. {question_index + 1} von 9
        **THEMA:** {schema['topic']}
        **FRAGETYP:** {schema['type']}
        **BEISPIEL:** "{schema['example']}"

        **WICHTIGE REGELN:**
        1. Formuliere die Frage OFFEN und NEUTRAL - keine Suggestionen
        2. Passe die Formulierung an den bisherigen Gesprächsverlauf an
        3. Beziehe dich auf konkrete Details aus vorherigen Antworten
        4. Vermeide Begriffe wie "IT", "Fachabteilung", "Management"
        5. Die Frage soll zum Erzählen einladen

        **BISHERIGER INTERVIEW-VERLAUF:**
        {previous_context}
        """
    }
```

### 3.3 Besonderheit: Keine RAG-Nutzung bei Intake

Ein wichtiges Designprinzip: **Intake-Fragen werden OHNE RAG-Kontext generiert.**

```python
def _next_dynamic_intake_question(self, session):
    # Intake-Fragen werden OHNE Dokumenten-Kontext generiert
    # um neutrale, allgemeine Fragen zu stellen
    question = self.question_generator.generate_single_intake_question(
        question_index=next_index,
        answers=answers,
        previous_questions=asked_questions,
        document_summary=""  # KEIN Dokumenten-Kontext für Intake
    )
```

**Begründung:** Die Intake-Phase soll die Rolle neutral ermitteln. Würde RAG-Kontext verwendet, könnten die Fragen unbewusst auf bestimmte Rollen oder Branchen zugeschnitten sein, was die Klassifikation verfälschen würde.

---

## 4. RAG-System Implementation

### 4.1 Technischer Aufbau

Das RAG-System ermöglicht kontextbezogene Fragen basierend auf hochgeladenen Dokumenten:

```python
class RAGSystem:
    def __init__(
        self,
        chunk_size: int = 1000,        # Textblock-Größe in Zeichen
        chunk_overlap: int = 200,       # Überlappung für Kontext-Erhalt
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        top_k: int = 3                  # Anzahl relevanter Dokumente pro Abfrage
    ):
        # Text-Splitter mit hierarchischen Trennzeichen
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]  # Priorität: Absätze > Zeilen > Wörter
        )
        
        # Lokales Embedding-Modell (kein API-Key benötigt)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # FAISS für schnelle Vektor-Ähnlichkeitssuche
        self.vectorstore: Optional[FAISS] = None
```

### 4.2 Chunking-Strategie

**Problem:** LLMs haben begrenzte Kontextfenster. Die bereitgestellten Dokumente (bis 322 Zeilen) müssen aufgeteilt werden.

**Lösung:** Überlappende Chunks mit 20% Überlappung:

```
chunk_size=1000, chunk_overlap=200

Dokument: |████████████████████████████████████████████████████|
Chunk 1:  |████████████|
Chunk 2:        |████████████|     (200 Zeichen Überlappung)
Chunk 3:              |████████████|
```

**Begründung der Parameter:**
- `chunk_size=1000`: Groß genug für zusammenhängenden Kontext, klein genug für Präzision
- `chunk_overlap=200`: Verhindert Informationsverlust an Chunk-Grenzen
- `separators=["\n\n", "\n", " ", ""]`: Bevorzugt natürliche Textgrenzen

### 4.3 Selektive RAG-Nutzung

**Wichtig:** RAG wird nicht für alle Fragen verwendet. Die Entscheidung basiert auf dem Themenfeld:

```python
def _next_dynamic_role_question(self, session):
    # RAG nur für technische/spezifische Themen
    rag_keywords = [
        "systemlandschaft", "datenmanagement", "automatisierung", 
        "schnittstellen", "architektur", "integration", "security", "compliance"
    ]
    
    if next_field and self.rag_system and self.rag_system.is_initialized:
        field_id, field_def = next_field
        theme_id = field_def.get("theme_id", "").lower()
        hint = field_def.get("hint", "").lower()
        
        # Prüfe ob Theme-ID oder Hint RAG-relevante Schlüsselwörter enthält
        use_rag_for_field = any(kw in theme_id or kw in hint for kw in rag_keywords)
        
        if use_rag_for_field:
            rag_context = self.rag_system.get_context_for_question(role_query)
            print(f"📚 RAG-Kontext für: {field_def.get('theme_name')}")
        else:
            print(f"ℹ️ Kein RAG-Kontext für: {field_def.get('theme_name')} (Interview-basiert)")
```

**Begründung:**
- **Mit RAG:** Technische Details, Systeminfos, Compliance → branchenspezifische Präzision
- **Ohne RAG:** Allgemeine Fragen, persönliche Einschätzungen → neutralere Antworten

### 4.4 Dokument-Laden und Initialisierung

```python
def initialize(self, file_paths: List[str]) -> bool:
    """Initialisiert RAG mit gegebenen Dateien."""
    logger.info(f"🔄 Initialisiere RAG-System mit {len(file_paths)} Dateien...")
    
    # Lade Dokumente (PDF und TXT unterstützt)
    self.documents = self.load_documents(file_paths)
    
    if not self.documents:
        self.is_initialized = False
        return False
    
    # Erstelle Chunks
    chunks = self.text_splitter.split_documents(self.documents)
    logger.info(f"📊 {len(chunks)} Chunks erstellt")
    
    # Erstelle Vektor-Index
    self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
    self.is_initialized = True
    return True

def _load_pdf(self, file_path: str) -> List[Document]:
    """Extrahiert Text aus PDF seitenweise."""
    reader = PdfReader(file_path)
    documents = []
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text.strip():
            doc = Document(
                page_content=text,
                metadata={
                    'source': os.path.basename(file_path),
                    'page': page_num + 1,
                    'file_path': file_path
                }
            )
            documents.append(doc)
    return documents
```

### 4.5 Automatische Initialisierung bei Session-Start

Existierende Dateien im Upload-Ordner werden automatisch geladen:

```python
def get_or_create_session(session_id, load_saved=True):
    # Lade existierende Dateien aus Upload-Ordner
    existing_files = get_existing_files()  # Scannt uploads/
    
    # ... Session erstellen ...
    
    # Initialisiere RAG-System mit existierenden Dateien
    if existing_files:
        logger.info(f"🔄 Initialisiere RAG mit {len(existing_files)} Dateien...")
        file_paths = [f['filepath'] for f in existing_files]
        rag_system.initialize(file_paths)
```

---

## 5. Rollenklassifikations-Algorithmus

### 5.1 Gewichteter Scoring-Algorithmus

Die Rollenklassifikation verwendet einen mehrstufigen Scoring-Algorithmus:

```python
class RoleClassifier:
    def classify(self, answers: Dict[str, str]) -> Dict[str, Any]:
        system = {
            "role": "system",
            "content": """
            **KLASSIFIKATIONS-ALGORITHMUS:**
            
            **Schritt 1: Ja/Nein-Antworten (höchstes Gewicht: +40%)**
            - "Operative Entscheidungen?" = JA → +40% für "fach"
            - "Technische Verantwortung?" = JA → +40% für "it"
            - "Projektleitung/Teams?" = JA → +40% für "management"
            
            **Schritt 2: Rollenbezeichnung analysieren (+30%)**
            - IT-Begriffe (Admin, Entwickler, DevOps) → +30% für "it"
            - Fach-Begriffe (Sachbearbeiter, Prozess) → +30% für "fach"
            - Management-Begriffe (Leiter, Manager) → +30% für "management"
            
            **Schritt 3: Aufgaben und Verantwortung (+15%)**
            - Technische Aufgaben (Server, API, Code) → +15% für "it"
            - Operative Aufgaben (Bearbeitung, Prüfung) → +15% für "fach"
            - Strategische Aufgaben (Planung, Budget) → +15% für "management"
            
            **Schritt 4: Probleme/Herausforderungen (+10%)**
            
            **Schritt 5: Erfolgsmessung (+5%)**
            
            **Regeln:**
            - Finale Scores zwischen 0.0 und 1.0
            - Bei widersprüchlichen Antworten: Alle Scores um 0.1 reduzieren
            
            Antworte im JSON-Format:
            {
              "candidates": [
                {"role": "it|fach|management", "score": 0.0-1.0},
                ...
              ],
              "explain": "Begründung"
            }
            """
        }
```

### 5.2 Konfidenz-Schwellenwert und Klärungsfragen

```python
def next_question(self, session):
    # Nach Intake: Rollenklassifikation durchführen
    result = self.classifier.classify(answers)
    session["role_candidates"] = result.get("candidates", [])
    
    top = session["role_candidates"][0] if session["role_candidates"] else None
    
    if top and top["score"] >= 0.7:  # 70% Konfidenz-Schwelle
        session["role"] = top["role"]
        session["phase"] = PHASE_ROLE
        print(f"✅ Rolle identifiziert: {top['role']} ({top['score']:.0%})")
    else:
        # Unsichere Klassifikation: Zusätzliche Klärungsfragen
        if len(session.get("clarifying_questions", [])) < 3:
            clarifying_q = self._generate_clarifying_question(session, top)
            if clarifying_q:
                session["clarifying_questions"].append(clarifying_q)
                return clarifying_q
        
        # Fallback: Top-Kandidat mit Markierung
        session["role"] = top["role"] if top else "fach"
        session["role_low_confidence"] = True
        session["phase"] = PHASE_ROLE
```

**Ablauf:**

```
Score ≥ 70%  →  Direkt zur rollenspezifischen Phase
Score < 70%  →  Bis zu 3 Klärungsfragen generieren
Nach 3 Fragen →  Top-Kandidat übernehmen (mit Warnung)
Kein Kandidat →  Fallback auf "fach"
```

### 5.3 JSON-Parsing und Fehlerbehandlung

```python
def _parse_llm_response(self, payload: str) -> Dict[str, Any]:
    """Robustes JSON-Parsing mit Fallback."""
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        # Fallback: Suche nach JSON-Block im Text
        m = re.search(r"\{.*\}", payload, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"Kein gültiges JSON gefunden: {payload}")

def _validate_and_normalize(self, result: Dict) -> Dict:
    """Normalisiert Rollen auf gültige Werte."""
    valid_roles = {"it", "fach", "management"}
    
    for candidate in result.get("candidates", []):
        role = candidate.get("role", "").lower()
        # Normalisiere Varianten
        if role in ["fachabteilung", "sachbearbeiter"]:
            role = "fach"
        elif role in ["führung", "leitung"]:
            role = "management"
        
        if role not in valid_roles:
            role = "fach"  # Default
        
        candidate["role"] = role
        candidate["score"] = max(0.0, min(1.0, candidate.get("score", 0.5)))
    
    return result
```

---

## 6. Interview-Engine und Phasensteuerung

### 6.1 Zwei-Phasen-Architektur

Die zentrale `InterviewEngine` steuert den gesamten Interview-Ablauf:

```python
class InterviewEngine:
    def __init__(self, repo, classifier, question_generator=None, 
                 use_dynamic_questions=True, demo_mode=False, 
                 rag_system=None, schema_manager=None):
        self.repo = repo
        self.classifier = classifier
        self.question_generator = question_generator
        self.use_dynamic_questions = use_dynamic_questions
        self.demo_mode = demo_mode
        self.rag_system = rag_system
        self.schema_manager = schema_manager or get_schema_manager()

    def next_question(self, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        phase = session.get("phase", PHASE_INTAKE)
        answers = session.setdefault("answers", {})
        
        if phase == PHASE_INTAKE:
            return self._handle_intake_phase(session)
        elif phase == PHASE_ROLE:
            return self._handle_role_phase(session)
        return None
```

### 6.2 Intake-Phase: Dynamische Fragengenerierung

```python
def _next_dynamic_intake_question(self, session):
    """Generiert Intake-Fragen einzeln mit LLM."""
    answers = session.get("answers", {})
    asked_questions = session.setdefault("intake_questions", [])
    
    # Prüfe auf unbeantwortete Fragen
    unanswered = self._unanswered(asked_questions, answers)
    if unanswered:
        return unanswered
    
    next_index = len(asked_questions)
    
    # Maximal 9 Intake-Fragen
    if next_index >= 9:
        print(f"✅ Alle {len(asked_questions)} Einstiegsfragen beantwortet")
        return None
    
    print(f"🤖 Generiere Intake-Frage #{next_index + 1} mit KI...")
    
    # WICHTIG: Intake ohne RAG-Kontext für Neutralität
    question = self.question_generator.generate_single_intake_question(
        question_index=next_index,
        answers=answers,
        previous_questions=asked_questions,
        document_summary=""  # Kein RAG!
    )
    
    if question:
        asked_questions.append(question)
        session["intake_questions"] = asked_questions
        return question
    
    return None
```

### 6.3 Rollenspezifische Phase: Schema-basierte Fragen

```python
def _next_dynamic_role_question(self, session):
    """Generiert schema-basierte Fragen für die ermittelte Rolle."""
    answers = session.get("answers", {})
    role = session.get("role")
    role_questions = session.setdefault("role_questions", [])
    filled_fields = session.setdefault("schema_fields", {})
    
    # Prüfe auf unbeantwortete Fragen
    unanswered = self._unanswered(role_questions, answers)
    if unanswered:
        return unanswered
    
    # Berechne Fortschritt
    progress = self.schema_manager.calculate_progress(role, filled_fields)
    
    print(f"📊 Schema-Fortschritt für '{role}':")
    print(f"   Ausgefüllt: {progress['filled_fields']}/{progress['total_fields']} ({progress['progress_percent']}%)")
    print(f"   Pflichtfelder: {progress['filled_required']}/{progress['required_fields']}")
    
    # Interview abgeschlossen?
    if progress["is_complete"]:
        print(f"🎉 Interview für Rolle '{role}' vollständig!")
        return None
    
    # Sicherheitscheck: Max. 20 Fragen
    if len(role_questions) >= self.question_generator.max_role_questions:
        print(f"⚠️ Maximum erreicht ({len(role_questions)} Fragen)")
        return None
    
    # Selektiver RAG-Kontext für technische Themen
    rag_context = self._get_selective_rag_context(role, filled_fields)
    
    # Generiere schema-basierte Frage
    role_question = self.question_generator.generate_schema_based_question(
        role=role,
        filled_fields=filled_fields,
        answers=answers,
        document_context=rag_context
    )
    
    if role_question:
        role_questions.append(role_question)
        session["role_questions"] = role_questions
        return role_question
    
    return None
```

### 6.4 Besonderheit: Streaming-Support

Für bessere UX unterstützt die Engine auch Streaming:

```python
def next_question_stream(self, session):
    """Generator-Variante für Streaming während der Generierung."""
    phase = session.get("phase", PHASE_INTAKE)
    
    if phase == PHASE_INTAKE:
        # Status-Updates während Generierung
        yield {"status": f"Generiere Frage {next_index + 1}/9..."}
        
        # Streaming der Fragen-Generierung
        for chunk in self.question_generator.generate_single_intake_question_stream(...):
            if isinstance(chunk, dict) and chunk.get("__complete__"):
                yield {"question": chunk.get("question"), "done": True}
                return
            else:
                yield {"chunk": chunk}  # Text-Chunk für Live-Anzeige
```

---

## 7. Schema-Manager und Fortschrittsverfolgung

### 7.1 Schema-Laden

```python
class RoleSchemaManager:
    def __init__(self, config_dir=None):
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config"
        )
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Lädt alle Schema-Dateien aus config/."""
        schema_files = {
            "fach": "role_schema_fach.json",
            "it": "role_schema_it.json",
            "management": "role_schema_management.json"
        }
        
        for role, filename in schema_files.items():
            filepath = os.path.join(self.config_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    self.schemas[role] = json.load(f)
                print(f"✅ Schema '{role}' geladen: {filename}")
```

### 7.2 Feld-Extraktion mit Themenfeld-Zuordnung

```python
def get_all_fields(self, role: str) -> Dict[str, Dict[str, Any]]:
    """Flacht die hierarchische Struktur für einfachen Zugriff."""
    schema = self.get_schema(role)
    if not schema:
        return {}
    
    all_fields = {}
    for theme_id, theme_data in schema.get("fields", {}).items():
        for field_id, field_def in theme_data.get("fields", {}).items():
            field_def_copy = field_def.copy()
            # Füge Theme-Kontext hinzu
            field_def_copy["theme_id"] = theme_id
            field_def_copy["theme_name"] = theme_data.get("name", theme_id)
            all_fields[field_id] = field_def_copy
    
    return all_fields
```

### 7.3 Fortschrittsberechnung

```python
def calculate_progress(self, role: str, filled_fields: Dict[str, Any]) -> Dict[str, Any]:
    """Berechnet detaillierten Interview-Fortschritt."""
    all_fields = self.get_all_fields(role)
    required_fields = self.get_required_fields(role)
    conditional_fields = self.get_conditional_fields(role)
    
    filled_count = 0
    filled_required_count = 0
    missing_required = []
    
    for field_id in all_fields:
        is_filled = field_id in filled_fields and filled_fields[field_id]
        
        if is_filled:
            filled_count += 1
            if field_id in required_fields:
                filled_required_count += 1
        else:
            if field_id in required_fields:
                missing_required.append(field_id)
    
    # Bedingte Felder prüfen
    for field_id, condition in conditional_fields.items():
        if self._evaluate_condition(condition, filled_fields):
            if all_fields[field_id].get("required") and field_id not in filled_fields:
                missing_required.append(field_id)
    
    total_required = len(required_fields)
    progress_percent = round(filled_required_count / total_required * 100, 1) if total_required > 0 else 100
    
    return {
        "total_fields": len(all_fields),
        "required_fields": total_required,
        "filled_fields": filled_count,
        "filled_required": filled_required_count,
        "progress_percent": progress_percent,
        "missing_required": missing_required,
        "is_complete": len(missing_required) == 0
    }
```

### 7.4 Bedingte Felder (Conditional Fields)

```python
def _evaluate_condition(self, condition: str, filled_fields: Dict) -> bool:
    """Evaluiert Bedingungen wie 'field_x == Ja' oder 'field_y contains Text'."""
    # Beispiel: "systeme_integriert == 'Ja, integriert'"
    if "==" in condition:
        field, value = condition.split("==")
        field = field.strip()
        value = value.strip().strip("'\"")
        return filled_fields.get(field) == value
    
    # Beispiel: "daten_zielsysteme contains 'Mehrere Systeme'"
    if "contains" in condition:
        field, value = condition.split("contains")
        field = field.strip()
        value = value.strip().strip("'\"")
        field_value = filled_fields.get(field, "")
        return value in str(field_value)
    
    return False
```

---

## 8. Session-Management und Persistenz

### 8.1 Thread-sichere Session-Verwaltung

```python
from threading import Lock

interview_sessions = {}
session_lock = Lock()

def get_or_create_session(session_id, load_saved=True):
    """Thread-sichere Session-Verwaltung."""
    with session_lock:
        if session_id not in interview_sessions:
            # Versuche gespeicherte Session zu laden
            saved_data = session_store.load_session(session_id) if load_saved else None
            
            if saved_data:
                logger.info(f"📂 Lade gespeicherte Session: {session_id}")
                session_data = saved_data
            else:
                logger.info(f"🆕 Erstelle neue Session: {session_id}")
                session_data = {
                    'phase': PHASE_INTAKE,
                    'answers': {},
                    'role': None,
                    'intake_questions': [],
                    'role_questions': [],
                    'uploaded_files': [],
                    'schema_fields': {},
                    'completed_interviews': [],
                    'current_interview_index': 0
                }
            
            # Initialisiere alle Komponenten
            interview_sessions[session_id] = {
                'engine': InterviewEngine(...),
                'doc_generator': DocGenerator(llm_client),
                'rag_system': RAGSystem(...),
                'session_data': session_data
            }
        
        return interview_sessions[session_id]
```

### 8.2 Auto-Save nach jeder Antwort

```python
AUTO_SAVE_ENABLED = True

def save_session(session_id: str):
    """Speichert Session persistent als JSON."""
    if not AUTO_SAVE_ENABLED:
        return
    
    if session_id in interview_sessions:
        session_data = interview_sessions[session_id]['session_data']
        session_store.save_session(session_id, session_data)

# In submit_answer():
@app.route('/api/answer', methods=['POST'])
def submit_answer():
    # ... Antwort verarbeiten ...
    
    # Auto-Save nach jeder Antwort
    save_session(session_id)
    
    return jsonify({...})
```

### 8.3 Session-Datenstruktur

```python
session_data = {
    # Phase-Tracking
    'phase': 'intake' | 'role_specific',
    'role': None | 'fach' | 'it' | 'management',
    'role_low_confidence': False,  # Markierung bei unsicherer Klassifikation
    
    # Fragen und Antworten
    'answers': {
        'question_id_1': 'Antworttext',
        'question_id_2': 'Ja',
        # ...
    },
    'intake_questions': [
        {'id': 'role_function', 'text': '...', 'type': 'text'},
        # ... 9 Fragen
    ],
    'role_questions': [
        {'id': 'position', 'text': '...', 'field_id': 'position', 'theme_name': 'Allgemein'},
        # ... schema-basierte Fragen
    ],
    
    # Schema-Felder (für Dokumentengenerierung)
    'schema_fields': {
        'position': 'Sachbearbeiter',
        'hauptaufgaben': ['Daten eingeben', 'Dokumente prüfen'],
        # ...
    },
    
    # Dateien
    'uploaded_files': [
        {'filename': 'doc.pdf', 'filepath': 'uploads/doc.pdf', 'size': 12345}
    ],
    
    # Multi-Interview-Support
    'completed_interviews': [],  # Für mehrere Rollen nacheinander
    'current_interview_index': 0,
    
    # Metadaten
    'session_name': 'Projekt X',
    'interview_complete': False
}
```

### 8.4 Session-Store Implementation

```python
class SessionStore:
    def __init__(self, storage_dir='sessions'):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
    
    def save_session(self, session_id: str, data: Dict):
        """Speichert Session als JSON-Datei."""
        filepath = os.path.join(self.storage_dir, f"{session_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        """Lädt Session aus JSON-Datei."""
        filepath = os.path.join(self.storage_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

# Singleton-Instanz
_session_store = None

def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
```

---

## 9. REST-API Implementation

### 9.1 Endpunkte

| Methode | Endpoint | Funktion |
|---------|----------|----------|
| POST | `/api/start` | Startet Interview, gibt erste Frage zurück |
| POST | `/api/answer` | Verarbeitet Antwort, gibt nächste Frage zurück |
| GET | `/api/status` | Gibt aktuellen Interview-Status zurück |
| POST | `/api/reset` | Setzt Interview zurück |
| POST | `/api/upload` | Lädt Datei hoch, initialisiert RAG |
| GET | `/api/files` | Liste der hochgeladenen Dateien |
| POST | `/api/generate-document` | Generiert Prozessdokumentation |
| GET | `/api/sessions` | Liste aller gespeicherten Sessions |

### 9.2 Start-Endpoint mit Preset-Rolle

```python
@app.route('/api/start', methods=['POST'])
def start_interview():
    data = request.json or {}
    session_id = data.get('session_id', 'default')
    preset_role = data.get('preset_role')  # Optional: Überspringt Intake
    session_name = data.get('session_name')
    
    interview = get_or_create_session(session_id)
    
    # Preset-Rolle: Direkt zur rollenspezifischen Phase
    if preset_role and preset_role in ['fach', 'it', 'management']:
        interview['session_data']['role'] = preset_role
        interview['session_data']['phase'] = PHASE_ROLE
        print(f"✅ Rolle '{preset_role}' voreingestellt, überspringe Intake")
    
    # Erste Frage generieren
    question = interview['engine'].next_question(interview['session_data'])
    
    save_session(session_id)
    
    return jsonify({
        'success': True,
        'question': question,
        'status': get_status_info(interview['session_data'])
    })
```

### 9.3 Answer-Endpoint mit Schema-Feld-Mapping

```python
@app.route('/api/answer', methods=['POST'])
def submit_answer():
    data = request.json
    session_id = data.get('session_id', 'default')
    question_id = data.get('question_id')
    answer_text = data.get('answer')
    
    interview = get_or_create_session(session_id)
    session_data = interview['session_data']
    
    # Antwort speichern
    session_data['answers'][question_id] = answer_text
    
    # Bei rollenspezifischen Fragen: Schema-Feld aktualisieren
    if session_data.get('phase') == PHASE_ROLE:
        role_questions = session_data.get('role_questions', [])
        current_question = next(
            (q for q in role_questions if q.get('id') == question_id), None
        )
        if current_question and current_question.get('field_id'):
            interview['engine'].process_role_answer(
                session_data, current_question, answer_text
            )
    
    # Nächste Frage holen
    next_question = interview['engine'].next_question(session_data)
    
    save_session(session_id)
    
    return jsonify({
        'success': True,
        'question': next_question,
        'status': get_status_info(session_data),
        'completed': next_question is None
    })
```

### 9.4 Status-Informationen

```python
def get_status_info(session_data: Dict) -> Dict:
    phase = session_data.get('phase', PHASE_INTAKE)
    role = session_data.get('role')
    
    phase_labels = {
        PHASE_INTAKE: 'Einstiegsfragen',
        PHASE_ROLE: 'Rollenspezifische Fragen'
    }
    
    role_labels = {
        'fach': 'Fachabteilung',
        'it': 'IT',
        'management': 'Management'
    }
    
    return {
        'phase': phase,
        'phase_label': phase_labels.get(phase, phase),
        'role': role,
        'role_label': role_labels.get(role, 'Nicht zugewiesen'),
        'answered_count': len(session_data.get('answers', {})),
        'files_count': len(session_data.get('uploaded_files', [])),
        'role_low_confidence': session_data.get('role_low_confidence', False),
        'is_complete': session_data.get('interview_complete', False)
    }
```

---

## 10. Fallback-Mechanismen und Fehlerbehandlung

### 10.1 Fallback-Fragen bei LLM-Fehler

```python
def _get_fallback_questions(self) -> List[Dict[str, Any]]:
    """Statische Fallback-Fragen wenn LLM nicht verfügbar."""
    return [
        {
            "id": "role_function",
            "text": "Welche Rolle bzw. Funktion haben Sie in Ihrem Unternehmen?",
            "type": "text",
            "required": True
        },
        {
            "id": "tasks_responsibility",
            "text": "Welche Aufgaben gehören zu Ihrem Verantwortungsbereich?",
            "type": "text",
            "required": True
        },
        # ... 7 weitere statische Fragen
        {
            "id": "operational_decisions",
            "text": "Treffen Sie hauptsächlich operative Entscheidungen im Tagesgeschäft?",
            "type": "choice",
            "options": ["Ja", "Nein"],
            "required": True
        },
        {
            "id": "technical_responsibility",
            "text": "Sind Sie für technische Systeme oder deren Betreuung verantwortlich?",
            "type": "choice",
            "options": ["Ja", "Nein"],
            "required": True
        },
        {
            "id": "project_leadership",
            "text": "Leiten Sie Projekte oder sind Sie für ein Team verantwortlich?",
            "type": "choice",
            "options": ["Ja", "Nein"],
            "required": True
        }
    ]
```

### 10.2 Fallback-Klassifikation

```python
def classify(self, answers):
    try:
        # LLM-Klassifikation
        response = self.llm.complete(messages=[system, user], json_mode={"type": "json_object"})
        result = self._parse_llm_response(response.choices[0].message.content)
        result["source"] = "llm"
        return self._validate_and_normalize(result)
        
    except Exception as e:
        print(f"❌ LLM-Klassifikation fehlgeschlagen: {e}")
        # Fallback: Unsichere Default-Klassifikation
        return {
            "candidates": [
                {"role": "fach", "score": 0.4},
                {"role": "it", "score": 0.3},
                {"role": "management", "score": 0.3}
            ],
            "explain": "Automatische Klassifikation fehlgeschlagen",
            "source": "fallback",
            "error": str(e)
        }
```

### 10.3 Fragen-Validierung

```python
def _validate_questions(self, questions: List[Dict]) -> List[Dict]:
    """Validiert und normalisiert LLM-generierte Fragen."""
    validated = []
    
    for q in questions:
        # Pflichtfelder prüfen
        if not q.get("id") or not q.get("text"):
            print(f"⚠️ Frage ohne ID oder Text übersprungen")
            continue
        
        # Typ normalisieren
        q_type = q.get("type", "text").lower()
        if q_type not in ["text", "choice", "multiple_choice", "number", "scale"]:
            q["type"] = "text"
        else:
            q["type"] = q_type
        
        # Choice-Fragen müssen Options haben
        if q["type"] == "choice" and not q.get("options"):
            q["options"] = ["Ja", "Nein"]
        
        # Required-Flag setzen
        q["required"] = q.get("required", True)
        
        validated.append(q)
    
    return validated
```

### 10.4 Graceful Degradation bei RAG-Fehler

```python
def get_context_for_question(self, query: str) -> str:
    """Holt relevanten Kontext aus dem Vektorstore."""
    if not self.is_initialized or not self.vectorstore:
        return ""  # Graceful degradation: Kein Kontext
    
    try:
        docs = self.vectorstore.similarity_search(query, k=self.top_k)
        context = "\n\n".join([doc.page_content for doc in docs])
        return context[:3000]  # Limit für Kontext-Fenster
    except Exception as e:
        logger.error(f"RAG-Fehler: {e}")
        return ""  # Weiter ohne Kontext
```

---

## Anhang

### A. Konfigurationsparameter

| Parameter | Standardwert | Beschreibung |
|-----------|-------------|--------------|
| `LOCAL_LLM_URL` | `http://localhost:11434` | Ollama Server URL |
| `LOCAL_LLM_MODEL` | `mistral-small` | Modellname |
| `MISTRAL_API_KEY` | - | Cloud API Key |
| `chunk_size` | 1000 | RAG Chunk-Größe (Zeichen) |
| `chunk_overlap` | 200 | RAG Chunk-Überlappung |
| `top_k` | 3 | Anzahl RAG-Ergebnisse |
| `role_confidence_threshold` | 0.7 | Klassifikations-Schwelle |
| `max_role_questions` | 20 | Max. rollenspezifische Fragen |
| `num_initial_questions` | 9 | Anzahl Intake-Fragen |

### B. Abhängigkeiten

```
Flask>=2.3.0
python-dotenv>=1.0.0
requests>=2.31.0
langchain>=0.1.0
langchain-community>=0.0.10
sentence-transformers>=2.2.0
faiss-cpu>=1.7.4
PyPDF2>=3.0.0
```

### C. Codeumfang

| Modul | Zeilen | Funktion |
|-------|--------|----------|
| `web_app.py` | 1332 | Flask-Server, API-Endpoints |
| `question_generator.py` | 1029 | LLM-basierte Fragengenerierung |
| `engine.py` | 657 | Interview-Steuerung |
| `mistral_client.py` | 550 | LLM-Client (Ollama + API) |
| `rag_system.py` | 441 | RAG-Implementation |
| `role_schema_manager.py` | 441 | Schema-Verwaltung |
| `role_classifier.py` | 228 | Rollenklassifikation |

**Gesamt: ~4.700 Zeilen Python-Code**

---

*Diese Dokumentation beschreibt die Backend-Implementierung des Interview-Orchestrators.*
