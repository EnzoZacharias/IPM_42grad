import os
import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.models import StartRequest, AnswerRequest, GapRequest, DocRequest
from app.llm.mistral_client import MistralClient
from interview.repo import QuestionRepo
from interview.role_classifier import RoleClassifier
from interview.question_generator import DynamicQuestionGenerator
from interview.engine import InterviewEngine, PHASE_INTAKE, PHASE_ROLE
from doc.generator import DocGenerator

load_dotenv()

app = FastAPI(title="Interview Orchestrator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# In-Memory Storage für Demo
SESSIONS: Dict[str, Dict[str, Any]] = {}

# Infrastruktur
repo = QuestionRepo(path=os.path.join(os.path.dirname(__file__), "..", "config", "questions.json"))
llm = MistralClient()
classifier = RoleClassifier(llm)
question_generator = DynamicQuestionGenerator(llm)
engine = InterviewEngine(
    repo=repo,
    classifier=classifier,
    question_generator=question_generator,
    use_dynamic_questions=True
)
doc = DocGenerator(llm)

# Automatischer Start beim Server-Start
@app.on_event("startup")
async def startup_event():
    print("\n" + "="*60)
    print("🚀 Interview Orchestrator gestartet!")
    print("="*60)
    
    # Automatisch eine Session erstellen
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "session_id": session_id,
        "phase": PHASE_INTAKE,
        "role": None,
        "answers": {},
        "questions": [],  # Speichert alle gestellten Fragen
        "role_candidates": []
    }
    
    # Erste Frage abrufen
    q = engine.next_question(SESSIONS[session_id])
    
    print(f"\n📋 Session erstellt: {session_id}")
    print(f"\n❓ Erste Frage:")
    print(f"   ID: {q.get('id')}")
    print(f"   Frage: {q.get('text')}")
    if q.get('type') == 'choice':
        print(f"   Optionen: {q.get('options')}")
    print(f"\n💡 Verwende diese Session-ID für /answer Requests")
    print("="*60 + "\n")

@app.post("/start")
def start(req: StartRequest):
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "session_id": session_id,
        "phase": PHASE_INTAKE,
        "role": None,
        "answers": {},
        "questions": [],  # Speichert alle gestellten Fragen
        "role_candidates": []
    }
    # optional: role_hint vorbefüllen
    if req.role_hint:
        SESSIONS[session_id]["answers"]["role_hint"] = req.role_hint

    q = engine.next_question(SESSIONS[session_id])
    if q:
        SESSIONS[session_id]["questions"].append(q)
    return {
        "session_id": session_id,
        "next_question": q,
        "state": {
            "phase": SESSIONS[session_id]["phase"],
            "role": SESSIONS[session_id]["role"]
        }
    }

@app.post("/answer")
def answer(req: AnswerRequest):
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    # Antwort speichern
    session["answers"][req.question_id] = req.value

    # Discriminator: Option → Rolle setzen
    for d in repo.discriminators():
        if d["id"] == req.question_id:
            opt_map = d.get("options_to_role", {})
            mapped_role = opt_map.get(str(req.value), "")
            if mapped_role:
                session["role"] = mapped_role
                session["phase"] = PHASE_ROLE

    q = engine.next_question(session)
    if q:
        session["questions"].append(q)
    return {
        "next_question": q,
        "state": {
            "phase": session.get("phase"),
            "role": session.get("role"),
            "role_low_confidence": session.get("role_low_confidence", False),
            "role_candidates": session.get("role_candidates", [])
        }
    }

@app.get("/status/{session_id}")
def status(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    return {
        "session_id": session_id,
        "phase": session.get("phase"),
        "role": session.get("role"),
        "answers": session.get("answers", {}),
        "role_candidates": session.get("role_candidates", []),
        "role_low_confidence": session.get("role_low_confidence", False)
    }

@app.post("/gaps")
def detect_gaps(req: GapRequest):
    # Simple Pflichtfeld-Check (du kannst später ein LLM daran hängen)
    missing = [qid for qid in req.required_ids if qid not in req.answers or not str(req.answers[qid]).strip()]
    clarify = []
    return {"missing": missing, "clarify": clarify}

@app.post("/document")
def build_document(req: DocRequest):
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    answers = session.get("answers", {})
    questions = session.get("questions", [])
    target = req.target.lower()

    # Nutze LLM-basierte Dokumentgenerierung
    txt = doc.render_it(questions, answers)

    return {"document": txt}
