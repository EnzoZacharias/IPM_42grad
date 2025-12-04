"""
Flask-Webanwendung für das Interview-System
Leichtgewichtige Web-UI mit Streaming, Reset-Funktion, Status-Anzeige und Dokument-Upload
Inkl. RAG-System für kontextbasierte Fragen aus hochgeladenen Dokumenten
Session-Persistenz für Fortsetzung nach Neustart
"""
import os
import json
import logging
from flask import Flask, render_template, request, jsonify, Response, session as flask_session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from threading import Lock
from app.llm.mistral_client import MistralClient, BACKEND_LOCAL, BACKEND_MISTRAL_API
from interview.repo import QuestionRepo
from interview.role_classifier import RoleClassifier
from interview.question_generator import DynamicQuestionGenerator
from interview.engine import InterviewEngine, PHASE_INTAKE, PHASE_ROLE
from interview.session_store import SessionStore, get_session_store
from doc.generator import DocGenerator
from rag.rag_system import RAGSystem

load_dotenv()

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt'}

# Erstelle Upload-Ordner falls nicht vorhanden
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Globale Variablen für die Interview-Engine
interview_sessions = {}
session_lock = Lock()

# Session Store für Persistenz
session_store = get_session_store()

# Auto-Save Intervall (nach jeder Antwort)
AUTO_SAVE_ENABLED = True

def allowed_file(filename):
    """Prüft ob die Dateiendung erlaubt ist"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_existing_files():
    """Scannt den Upload-Ordner nach existierenden Dateien"""
    existing_files = []
    upload_dir = app.config['UPLOAD_FOLDER']
    
    if not os.path.exists(upload_dir):
        return existing_files
    
    for filename in os.listdir(upload_dir):
        if allowed_file(filename):
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath):
                existing_files.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': os.path.getsize(filepath)
                })
    
    logger.info(f"📁 {len(existing_files)} existierende Dateien im Upload-Ordner gefunden")
    return existing_files

def get_or_create_session(session_id, load_saved: bool = True):
    """Holt oder erstellt eine Interview-Session (thread-safe)"""
    with session_lock:
        if session_id not in interview_sessions:
            # Prüfe ob eine gespeicherte Session existiert
            saved_data = None
            if load_saved:
                saved_data = session_store.load_session(session_id)
            
            if saved_data:
                logger.info(f"📂 Lade gespeicherte Session: {session_id}")
            else:
                logger.info(f"🆕 Erstelle NEUE Session: {session_id}")
            
            # Initialisiere Interview-Komponenten
            # Prüfe zuerst ob lokales Ollama verfügbar ist, sonst Mistral API
            temp_client = MistralClient(backend=BACKEND_LOCAL)
            if temp_client.is_local_available():
                logger.info("🏠 Lokales Ollama Backend verfügbar - verwende lokales Backend")
                llm_client = temp_client
            else:
                mistral_api_key = os.getenv("MISTRAL_API_KEY", "")
                if mistral_api_key:
                    logger.info("🔑 Lokales Backend nicht verfügbar - verwende Mistral API Backend")
                    llm_client = MistralClient(backend=BACKEND_MISTRAL_API, api_key=mistral_api_key)
                else:
                    logger.warning("⚠️ Weder Ollama noch Mistral API verfügbar - verwende lokales Backend (wird fehlschlagen)")
                    llm_client = temp_client
            
            questions_path = os.path.join(os.path.dirname(__file__), "config", "questions.json")
            repo = QuestionRepo(path=questions_path)
            classifier = RoleClassifier(llm_client, repo)
            question_generator = DynamicQuestionGenerator(llm_client)
            
            # Initialisiere RAG-System
            rag_system = RAGSystem(
                chunk_size=1000,
                chunk_overlap=200,
                top_k=3
            )
            
            # Lade existierende Dateien aus Upload-Ordner
            existing_files = get_existing_files()
            
            # Demo-Modus aktiviert: Stoppt nach Rollenklassifikation
            engine = InterviewEngine(
                repo, 
                classifier, 
                question_generator, 
                use_dynamic_questions=True, 
                demo_mode=False,
                rag_system=rag_system
            )
            
            # Wenn gespeicherte Session existiert, stelle sie wieder her
            if saved_data:
                session_data = saved_data
                # Aktualisiere uploaded_files mit aktuellen Dateien
                session_data['uploaded_files'] = existing_files
                logger.info(f"   Phase: {session_data.get('phase')}")
                logger.info(f"   Rolle: {session_data.get('role')}")
                logger.info(f"   Antworten: {len(session_data.get('answers', {}))}")
                logger.info(f"   Abgeschlossene Interviews: {len(session_data.get('completed_interviews', []))}")
            else:
                session_data = {
                    'phase': PHASE_INTAKE,
                    'answers': {},
                    'role': None,
                    'intake_questions': [],
                    'role_questions': [],
                    'uploaded_files': existing_files,
                    'schema_fields': {},
                    # Multi-Rollen-Support
                    'completed_interviews': [],
                    'current_interview_index': 0
                }
            
            interview_sessions[session_id] = {
                'engine': engine,
                'doc_generator': DocGenerator(llm_client),
                'rag_system': rag_system,
                'session_data': session_data
            }
            
            # Initialisiere RAG-System mit existierenden Dateien
            if existing_files:
                logger.info(f"🔄 Initialisiere RAG-System mit {len(existing_files)} existierenden Dateien...")
                file_paths = [f['filepath'] for f in existing_files]
                rag_system.initialize(file_paths)
        else:
            logger.info(f"♻️  Verwende EXISTIERENDE Session: {session_id}")
            logger.info(f"   Anzahl intake_questions: {len(interview_sessions[session_id]['session_data'].get('intake_questions', []))}")
            logger.info(f"   Anzahl Antworten: {len(interview_sessions[session_id]['session_data'].get('answers', {}))}")
        
        return interview_sessions[session_id]


def save_session(session_id: str):
    """Speichert die aktuelle Session persistent."""
    if not AUTO_SAVE_ENABLED:
        return
    
    if session_id in interview_sessions:
        session_data = interview_sessions[session_id]['session_data']
        session_store.save_session(session_id, session_data)

@app.route('/')
def index():
    """Hauptseite"""
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_interview():
    """Startet ein neues Interview"""
    data = request.json or {}
    session_id = data.get('session_id', 'default')
    preset_role = data.get('preset_role')  # Optional: Voreingestellte Rolle
    session_name = data.get('session_name')  # Optional: Projektname
    
    print(f"\n🚀 /api/start aufgerufen für Session: {session_id}")
    if preset_role:
        print(f"   📌 Voreingestellte Rolle: {preset_role}")
    if session_name:
        print(f"   📝 Projektname: {session_name}")
    
    interview = get_or_create_session(session_id)
    
    # Speichere den Session-Namen/Projektnamen
    if session_name:
        interview['session_data']['session_name'] = session_name
    
    # Falls eine Rolle voreingestellt ist, setze sie direkt
    if preset_role and preset_role in ['fach', 'it', 'management']:
        interview['session_data']['role'] = preset_role
        interview['session_data']['phase'] = PHASE_ROLE
        
        # Rolle-Label setzen
        role_labels = {
            'fach': 'Fachabteilung',
            'it': 'IT',
            'management': 'Management'
        }
        interview['session_data']['role_label'] = role_labels.get(preset_role, preset_role)
        
        # Schema-Felder für die Rolle initialisieren
        if hasattr(interview['engine'], 'schema_manager'):
            schema_fields = interview['engine'].schema_manager.get_role_fields(preset_role)
            # schema_fields ist eine Liste - konvertiere nicht hier, das macht die Engine
        
        print(f"   ✅ Rolle '{preset_role}' direkt gesetzt, überspringe Intake-Phase")
    
    # Setze Prozess-Status
    interview['session_data']['process_status'] = 'Generiere Einstiegsfragen mit KI...'
    
    # Hole die erste Frage
    question = interview['engine'].next_question(interview['session_data'])
    
    print(f"📊 Nach next_question: intake_questions = {len(interview['session_data'].get('intake_questions', []))}")
    
    # Lösche Prozess-Status
    interview['session_data']['process_status'] = None
    
    # Speichere Session
    save_session(session_id)
    
    if question:
        return jsonify({
            'success': True,
            'question': question,
            'status': get_status_info(interview['session_data'])
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Keine Frage verfügbar'
        })

@app.route('/api/answer', methods=['POST'])
def submit_answer():
    """Verarbeitet eine Antwort und gibt die nächste Frage zurück"""
    data = request.json
    session_id = data.get('session_id', 'default')
    question_id = data.get('question_id')
    answer_text = data.get('answer')
    
    interview = get_or_create_session(session_id)
    session_data = interview['session_data']
    
    # Speichere Antwort
    session_data['answers'][question_id] = answer_text
    
    # Verarbeite Antwort für Schema-Felder (bei rollenspezifischen Fragen)
    if session_data.get('phase') == PHASE_ROLE:
        role_questions = session_data.get('role_questions', [])
        # Finde die aktuelle Frage
        current_question = next(
            (q for q in role_questions if q.get('id') == question_id),
            None
        )
        if current_question and current_question.get('field_id'):
            # Nutze die Engine-Methode zur Antwortverarbeitung
            interview['engine'].process_role_answer(
                session_data,
                current_question,
                answer_text
            )
    
    # Prüfe ob wir am Ende der Intake-Phase sind (für Rollenklassifikation)
    intake_questions = session_data.get('intake_questions', [])
    if intake_questions:
        answered_intake = sum(1 for q in intake_questions if q['id'] in session_data['answers'])
        if answered_intake == len(intake_questions) and session_data.get('phase') == 'intake':
            session_data['process_status'] = 'Analysiere Antworten und klassifiziere Rolle...'
    
    # Hole nächste Frage
    next_question = interview['engine'].next_question(session_data)
    
    # Prüfe ob Rolle gerade gesetzt wurde
    if session_data.get('role') and not session_data.get('role_announced'):
        session_data['role_announced'] = True
        session_data['process_status'] = f"Rolle '{session_data['role']}' identifiziert. Generiere rollenspezifische Fragen..."
    elif next_question and session_data.get('phase') == 'role_specific':
        session_data['process_status'] = 'Generiere nächste rollenspezifische Frage...'
    else:
        session_data['process_status'] = None
    
    # Auto-Save nach jeder Antwort
    save_session(session_id)
    
    return jsonify({
        'success': True,
        'question': next_question,
        'status': get_status_info(session_data),
        'completed': next_question is None,
        'process_status': session_data.get('process_status')
    })

@app.route('/api/chat', methods=['POST'])
def chat_stream():
    """Streaming-Endpoint für Chat-Antworten"""
    data = request.json
    session_id = data.get('session_id', 'default')
    message = data.get('message')
    
    interview = get_or_create_session(session_id)
    
    def generate():
        """Generator für Server-Sent Events"""
        # Simuliere Streaming (hier könnte echtes LLM-Streaming implementiert werden)
        response_text = f"Echo: {message}"
        
        for char in response_text:
            yield f"data: {json.dumps({'chunk': char})}\n\n"
        
        yield f"data: {json.dumps({'done': True})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/next-question-stream', methods=['POST'])
def next_question_stream():
    """Streaming-Endpoint für die nächste Frage mit Live-Generierung"""
    data = request.json
    session_id = data.get('session_id', 'default')
    
    interview = get_or_create_session(session_id)
    session_data = interview['session_data']
    
    def generate():
        """Generator für Server-Sent Events bei Fragen-Generierung"""
        try:
            for result in interview['engine'].next_question_stream(session_data):
                if isinstance(result, dict):
                    if result.get('status'):
                        # Status-Update
                        yield f"data: {json.dumps({'type': 'status', 'message': result['status']})}\n\n"
                    elif result.get('chunk'):
                        # Text-Chunk während Generierung
                        yield f"data: {json.dumps({'type': 'chunk', 'text': result['chunk']})}\n\n"
                    elif result.get('done'):
                        # Generierung abgeschlossen
                        question = result.get('question')
                        status = get_status_info(session_data)
                        yield f"data: {json.dumps({'type': 'complete', 'question': question, 'status': status, 'role_classified': result.get('role_classified', False)})}\n\n"
                        break
        except Exception as e:
            logger.error(f"Fehler bei Streaming: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/api/answer-stream', methods=['POST'])
def submit_answer_stream():
    """Streaming-Endpoint für Antworten mit Live-Generierung der Folgefrage"""
    data = request.json
    session_id = data.get('session_id', 'default')
    question_id = data.get('question_id')
    answer_text = data.get('answer')
    
    interview = get_or_create_session(session_id)
    session_data = interview['session_data']
    
    # Speichere Antwort
    session_data['answers'][question_id] = answer_text
    
    # Verarbeite Antwort für Schema-Felder (bei rollenspezifischen Fragen)
    if session_data.get('phase') == PHASE_ROLE:
        role_questions = session_data.get('role_questions', [])
        # Finde die aktuelle Frage
        current_question = next(
            (q for q in role_questions if q.get('id') == question_id),
            None
        )
        if current_question and current_question.get('field_id'):
            # Nutze die Engine-Methode zur Antwortverarbeitung
            interview['engine'].process_role_answer(
                session_data,
                current_question,
                answer_text
            )
    
    def generate():
        """Generator für Server-Sent Events"""
        try:
            # Generiere nächste Frage mit Streaming
            for result in interview['engine'].next_question_stream(session_data):
                if isinstance(result, dict):
                    if result.get('status'):
                        yield f"data: {json.dumps({'type': 'status', 'message': result['status']})}\n\n"
                    elif result.get('chunk'):
                        yield f"data: {json.dumps({'type': 'chunk', 'text': result['chunk']})}\n\n"
                    elif result.get('done'):
                        question = result.get('question')
                        status = get_status_info(session_data)
                        completed = question is None
                        # Auto-Save nach jeder Antwort (auch bei Streaming)
                        save_session(session_id)
                        
                        # Bei Rollenklassifizierung: Erst Rolle senden, dann Frage
                        if result.get('role_classified'):
                            yield f"data: {json.dumps({'type': 'role_classified', 'status': status})}\n\n"
                        
                        yield f"data: {json.dumps({'type': 'complete', 'question': question, 'status': status, 'completed': completed, 'role_classified': False})}\n\n"
                        break
        except Exception as e:
            logger.error(f"Fehler bei Answer-Streaming: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Gibt den aktuellen Interview-Fortschritt zurück"""
    session_id = request.args.get('session_id', 'default')
    
    if session_id not in interview_sessions:
        return jsonify({
            'success': False,
            'message': 'Session nicht gefunden'
        }), 404
    
    interview = interview_sessions[session_id]
    session_data = interview['session_data']
    
    # Hole detaillierten Fortschritt von der Engine
    progress = interview['engine'].get_interview_progress(session_data)
    
    return jsonify({
        'success': True,
        'progress': progress,
        'status': get_status_info(session_data)
    })

@app.route('/api/schema', methods=['GET'])
def get_filled_schema():
    """Gibt das ausgefüllte Schema für die aktuelle Rolle zurück"""
    session_id = request.args.get('session_id', 'default')
    
    if session_id not in interview_sessions:
        return jsonify({
            'success': False,
            'message': 'Session nicht gefunden'
        }), 404
    
    interview = interview_sessions[session_id]
    session_data = interview['session_data']
    
    # Hole das ausgefüllte Schema
    schema = interview['engine'].get_filled_schema(session_data)
    
    return jsonify({
        'success': True,
        'schema': schema
    })


@app.route('/api/interview/complete', methods=['POST'])
def complete_current_interview():
    """Schließt das aktuelle Rollen-Interview ab und speichert es"""
    data = request.json
    session_id = data.get('session_id', 'default')
    
    if session_id not in interview_sessions:
        return jsonify({
            'success': False,
            'message': 'Session nicht gefunden'
        }), 404
    
    interview = interview_sessions[session_id]
    session_data = interview['session_data']
    
    # Prüfe ob es Daten gibt die gespeichert werden können
    if not session_data.get('role'):
        return jsonify({
            'success': False,
            'message': 'Keine Rolle identifiziert - Interview kann nicht abgeschlossen werden'
        }), 400
    
    # Erstelle Interview-Zusammenfassung
    role_label = {
        'fachabteilung': 'Fachabteilung',
        'it': 'IT',
        'management': 'Management'
    }.get(session_data.get('role'), session_data.get('role'))
    
    completed_interview = {
        'role': session_data.get('role'),
        'role_label': role_label,
        'answers': dict(session_data.get('answers', {})),
        'schema_fields': dict(session_data.get('schema_fields', {})),
        'intake_questions': list(session_data.get('intake_questions', [])),
        'role_questions': list(session_data.get('role_questions', [])),
        'completed_at': __import__('datetime').datetime.now().isoformat(),
        'progress': interview['engine'].get_interview_progress(session_data)
    }
    
    # Füge zu completed_interviews hinzu
    if 'completed_interviews' not in session_data:
        session_data['completed_interviews'] = []
    session_data['completed_interviews'].append(completed_interview)
    
    # Speichere Session
    save_session(session_id)
    
    return jsonify({
        'success': True,
        'message': f'Interview für Rolle "{role_label}" abgeschlossen',
        'completed_interview': {
            'role': completed_interview['role'],
            'role_label': completed_interview['role_label'],
            'answered_questions': len(completed_interview['answers']),
            'progress': completed_interview['progress']
        },
        'total_completed': len(session_data['completed_interviews'])
    })


@app.route('/api/interview/new', methods=['POST'])
def start_new_role_interview():
    """Startet ein neues Rollen-Interview innerhalb der Session"""
    data = request.json
    session_id = data.get('session_id', 'default')
    
    if session_id not in interview_sessions:
        return jsonify({
            'success': False,
            'message': 'Session nicht gefunden'
        }), 404
    
    interview = interview_sessions[session_id]
    session_data = interview['session_data']
    
    # Speichere aktuelles Interview falls Fortschritt vorhanden
    if session_data.get('role') and len(session_data.get('answers', {})) > 0:
        # Auto-Complete des aktuellen Interviews
        role_label = {
            'fachabteilung': 'Fachabteilung',
            'it': 'IT',
            'management': 'Management'
        }.get(session_data.get('role'), session_data.get('role'))
        
        completed_interview = {
            'role': session_data.get('role'),
            'role_label': role_label,
            'answers': dict(session_data.get('answers', {})),
            'schema_fields': dict(session_data.get('schema_fields', {})),
            'intake_questions': list(session_data.get('intake_questions', [])),
            'role_questions': list(session_data.get('role_questions', [])),
            'completed_at': __import__('datetime').datetime.now().isoformat(),
            'progress': interview['engine'].get_interview_progress(session_data)
        }
        
        if 'completed_interviews' not in session_data:
            session_data['completed_interviews'] = []
        session_data['completed_interviews'].append(completed_interview)
    
    # Setze Session für neues Interview zurück (behalte completed_interviews)
    completed_interviews = session_data.get('completed_interviews', [])
    uploaded_files = session_data.get('uploaded_files', [])
    
    session_data.clear()
    session_data.update({
        'phase': PHASE_INTAKE,
        'answers': {},
        'role': None,
        'intake_questions': [],
        'role_questions': [],
        'uploaded_files': uploaded_files,
        'schema_fields': {},
        'completed_interviews': completed_interviews,
        'current_interview_index': len(completed_interviews)
    })
    
    # Generiere erste Frage für neues Interview
    question = interview['engine'].next_question(session_data)
    
    # Speichere Session
    save_session(session_id)
    
    return jsonify({
        'success': True,
        'message': 'Neues Rollen-Interview gestartet',
        'question': question,
        'status': get_status_info(session_data),
        'completed_interviews': len(completed_interviews)
    })


@app.route('/api/interview/completed', methods=['GET'])
def get_completed_interviews():
    """Gibt alle abgeschlossenen Interviews der Session zurück"""
    session_id = request.args.get('session_id', 'default')
    
    if session_id not in interview_sessions:
        # Versuche aus gespeicherter Session zu laden
        saved_data = session_store.load_session(session_id)
        if saved_data:
            completed = saved_data.get('completed_interviews', [])
        else:
            completed = []
    else:
        session_data = interview_sessions[session_id]['session_data']
        completed = session_data.get('completed_interviews', [])
    
    # Erstelle Übersicht
    interviews_summary = []
    for idx, interview_data in enumerate(completed):
        interviews_summary.append({
            'index': idx,
            'role': interview_data.get('role'),
            'role_label': interview_data.get('role_label'),
            'answered_questions': len(interview_data.get('answers', {})),
            'progress': interview_data.get('progress', {}),
            'completed_at': interview_data.get('completed_at')
        })
    
    return jsonify({
        'success': True,
        'completed_interviews': interviews_summary,
        'total': len(interviews_summary)
    })


@app.route('/api/interview/switch', methods=['POST'])
def switch_to_interview():
    """Wechselt zu einem bestimmten Interview (abgeschlossen oder aktuell)"""
    data = request.json
    session_id = data.get('session_id', 'default')
    target_index = data.get('interview_index')  # None = aktuelles Interview
    
    if session_id not in interview_sessions:
        # Versuche Session zu laden
        interview = get_or_create_session(session_id)
        if not interview:
            return jsonify({
                'success': False,
                'message': 'Session nicht gefunden'
            }), 404
    
    interview = interview_sessions[session_id]
    session_data = interview['session_data']
    completed_interviews = session_data.get('completed_interviews', [])
    current_index = session_data.get('current_interview_index', len(completed_interviews))
    
    # Speichere aktuelles Interview bevor wir wechseln
    if session_data.get('role') and len(session_data.get('answers', {})) > 0:
        # Prüfe ob das aktuelle Interview bereits in completed_interviews ist
        if current_index >= len(completed_interviews):
            # Aktuelles Interview ist noch nicht abgeschlossen - speichere es temporär
            role_label = {
                'fachabteilung': 'Fachabteilung',
                'it': 'IT',
                'management': 'Management'
            }.get(session_data.get('role'), session_data.get('role'))
            
            current_interview_data = {
                'role': session_data.get('role'),
                'role_label': role_label,
                'answers': dict(session_data.get('answers', {})),
                'schema_fields': dict(session_data.get('schema_fields', {})),
                'intake_questions': list(session_data.get('intake_questions', [])),
                'role_questions': list(session_data.get('role_questions', [])),
                'chat_history': list(session_data.get('chat_history', [])),
                'progress': interview['engine'].get_interview_progress(session_data),
                'is_current': True
            }
            completed_interviews.append(current_interview_data)
            session_data['completed_interviews'] = completed_interviews
    
    # Bestimme Ziel-Interview
    if target_index is None or target_index >= len(completed_interviews):
        # Bleibe beim/wechsle zum aktuellen Interview
        target_index = len(completed_interviews) - 1 if completed_interviews else 0
    
    if target_index < 0 or target_index >= len(completed_interviews):
        return jsonify({
            'success': False,
            'message': 'Ungültiger Interview-Index'
        }), 400
    
    # Lade das Ziel-Interview
    target_interview = completed_interviews[target_index]
    
    # Entferne das Ziel-Interview aus der Liste (es wird zum aktuellen)
    # Alle anderen bleiben in completed_interviews
    remaining_completed = [
        iv for i, iv in enumerate(completed_interviews) 
        if i != target_index
    ]
    
    # Aktualisiere Session mit dem Ziel-Interview
    uploaded_files = session_data.get('uploaded_files', [])
    
    session_data.clear()
    session_data.update({
        'phase': PHASE_ROLE if target_interview.get('role') else PHASE_INTAKE,
        'answers': dict(target_interview.get('answers', {})),
        'role': target_interview.get('role'),
        'intake_questions': list(target_interview.get('intake_questions', [])),
        'role_questions': list(target_interview.get('role_questions', [])),
        'uploaded_files': uploaded_files,
        'schema_fields': dict(target_interview.get('schema_fields', {})),
        'chat_history': list(target_interview.get('chat_history', [])),
        'completed_interviews': remaining_completed,
        'current_interview_index': len(remaining_completed)
    })
    
    # Speichere Session
    save_session(session_id)
    
    # Baue Chat-Historie für Frontend
    chat_history = []
    
    # Intake-Fragen und Antworten
    for q in session_data.get('intake_questions', []):
        q_id = q.get('id', '')
        chat_history.append({
            'type': 'question',
            'text': q.get('text', ''),
            'id': q_id
        })
        if q_id in session_data.get('answers', {}):
            chat_history.append({
                'type': 'answer',
                'text': session_data['answers'][q_id]
            })
    
    # Rollenspezifische Fragen und Antworten
    for q in session_data.get('role_questions', []):
        field_id = q.get('field_id', '')
        chat_history.append({
            'type': 'question',
            'text': q.get('text', ''),
            'field_id': field_id,
            'theme_name': q.get('theme_name', '')
        })
        if field_id in session_data.get('schema_fields', {}):
            field_data = session_data['schema_fields'][field_id]
            # Unterstütze beide Formate: String (alt) oder Dict (neu)
            if isinstance(field_data, dict):
                answer_text = field_data.get('raw_answer', field_data.get('value', ''))
            else:
                answer_text = str(field_data) if field_data else ''
            chat_history.append({
                'type': 'answer',
                'text': answer_text
            })
    
    # Hole nächste Frage
    next_question = interview['engine'].next_question(session_data)
    
    return jsonify({
        'success': True,
        'message': f"Wechsel zu Interview: {target_interview.get('role_label', 'Unbekannt')}",
        'status': get_status_info(session_data),
        'chat_history': chat_history,
        'next_question': next_question,
        'switched_to': {
            'role': target_interview.get('role'),
            'role_label': target_interview.get('role_label'),
            'answered_questions': len(session_data.get('answers', {}))
        }
    })


@app.route('/api/reset', methods=['POST'])
def reset_interview():
    """Setzt das Interview zurück"""
    session_id = request.json.get('session_id', 'default')
    
    # Lösche die gespeicherte Session
    session_store.delete_session(session_id)
    
    # Lösche die In-Memory Session
    if session_id in interview_sessions:
        del interview_sessions[session_id]
    
    # Erstelle neue Session (ohne gespeicherte Daten zu laden)
    interview = get_or_create_session(session_id, load_saved=False)
    question = interview['engine'].next_question(interview['session_data'])
    
    return jsonify({
        'success': True,
        'message': 'Interview wurde zurückgesetzt',
        'question': question,
        'status': get_status_info(interview['session_data'])
    })


@app.route('/api/sessions', methods=['GET'])
def list_saved_sessions():
    """Listet alle gespeicherten Sessions auf"""
    sessions = session_store.list_sessions()
    return jsonify({
        'success': True,
        'sessions': sessions
    })


@app.route('/api/sessions/latest', methods=['GET'])
def get_latest_session():
    """Gibt die zuletzt gespeicherte Session zurück"""
    latest = session_store.get_latest_session()
    
    if latest:
        return jsonify({
            'success': True,
            'has_saved_session': True,
            'session_id': latest['session_id'],
            'info': latest['info']
        })
    
    return jsonify({
        'success': True,
        'has_saved_session': False
    })


@app.route('/api/sessions/resume', methods=['POST'])
def resume_session():
    """Setzt eine gespeicherte Session fort"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({
            'success': False,
            'message': 'Keine Session-ID angegeben'
        }), 400
    
    # Prüfe ob Session existiert
    if not session_store.session_exists(session_id):
        return jsonify({
            'success': False,
            'message': 'Session nicht gefunden'
        }), 404
    
    # Lade die Session
    interview = get_or_create_session(session_id, load_saved=True)
    session_data = interview['session_data']
    
    # Erstelle Chat-History für Frontend
    history = []
    answers = session_data.get('answers', {})
    intake_questions = session_data.get('intake_questions', [])
    role_questions = session_data.get('role_questions', [])
    
    # Füge Intake-Fragen und Antworten hinzu
    for q in intake_questions:
        entry = {'question': q.get('text', '')}
        if q.get('id') in answers:
            entry['answer'] = answers[q['id']]
        history.append(entry)
    
    # Füge Rollen-Fragen und Antworten hinzu
    for q in role_questions:
        entry = {'question': q.get('text', '')}
        if q.get('id') in answers:
            entry['answer'] = answers[q['id']]
        history.append(entry)
    
    # Bestimme die nächste Frage basierend auf dem Fortschritt
    next_question = None
    
    if session_data.get('phase') == PHASE_INTAKE:
        # Prüfe ob noch Intake-Fragen offen sind
        for q in intake_questions:
            if q.get('id') not in answers:
                next_question = q
                break
        
        # Falls alle Intake-Fragen beantwortet, generiere nächste
        if not next_question and len(intake_questions) < 9:
            next_question = interview['engine'].next_question(session_data)
    
    elif session_data.get('phase') == PHASE_ROLE:
        # Generiere nächste rollenspezifische Frage
        next_question = interview['engine'].next_question(session_data)
    
    return jsonify({
        'success': True,
        'message': f"Session '{session_id}' fortgesetzt",
        'question': next_question,
        'current_question': next_question,
        'history': history,
        'status': get_status_info(session_data),
        'session_restored': True,
        'answers_count': len(answers)
    })


@app.route('/api/sessions/save', methods=['POST'])
def save_current_session():
    """Speichert die aktuelle Session manuell"""
    data = request.json
    session_id = data.get('session_id', 'default')
    
    if session_id not in interview_sessions:
        return jsonify({
            'success': False,
            'message': 'Keine aktive Session gefunden'
        }), 404
    
    session_data = interview_sessions[session_id]['session_data']
    success = session_store.save_session(session_id, session_data)
    
    return jsonify({
        'success': success,
        'message': 'Session gespeichert' if success else 'Fehler beim Speichern'
    })


@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_saved_session(session_id):
    """Löscht eine gespeicherte Session"""
    success = session_store.delete_session(session_id)
    
    return jsonify({
        'success': success,
        'message': 'Session gelöscht' if success else 'Session nicht gefunden'
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """Gibt den aktuellen Status zurück"""
    session_id = request.args.get('session_id', 'default')
    interview = get_or_create_session(session_id)
    
    return jsonify({
        'success': True,
        'status': get_status_info(interview['session_data'])
    })

@app.route('/api/upload', methods=['POST'])
def upload_document():
    """Dokument-Upload Endpoint - lädt Dateien hoch und re-initialisiert RAG-System"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt'}), 400
    
    file = request.files['file']
    session_id = request.form.get('session_id', 'default')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'success': False, 
            'message': f'Dateiformat nicht unterstützt. Erlaubt sind: {", ".join(app.config["ALLOWED_EXTENSIONS"])}'
        }), 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Speichere Dateiinfo in Session
        interview = get_or_create_session(session_id)
        interview['session_data']['uploaded_files'].append({
            'filename': filename,
            'filepath': filepath,
            'size': os.path.getsize(filepath)
        })
        
        # Re-initialisiere RAG-System mit allen hochgeladenen Dateien
        logger.info(f"📤 Datei hochgeladen: {filename}")
        all_files = [f['filepath'] for f in interview['session_data']['uploaded_files']]
        
        rag_system = interview.get('rag_system')
        if rag_system:
            logger.info(f"🔄 Re-initialisiere RAG-System mit {len(all_files)} Dateien...")
            success = rag_system.initialize(all_files)
            
            if success:
                stats = rag_system.get_stats()
                logger.info(f"✅ RAG-System initialisiert: {stats}")
                return jsonify({
                    'success': True,
                    'message': f'Datei "{filename}" erfolgreich hochgeladen und indexiert',
                    'file': {
                        'filename': filename,
                        'size': os.path.getsize(filepath)
                    },
                    'rag_stats': stats
                })
            else:
                logger.warning("⚠️  RAG-Initialisierung fehlgeschlagen")
                return jsonify({
                    'success': True,
                    'message': f'Datei "{filename}" hochgeladen, aber Indexierung fehlgeschlagen',
                    'file': {
                        'filename': filename,
                        'size': os.path.getsize(filepath)
                    }
                })
        
        return jsonify({
            'success': True,
            'message': f'Datei "{filename}" erfolgreich hochgeladen',
            'file': {
                'filename': filename,
                'size': os.path.getsize(filepath)
            }
        })

@app.route('/api/files', methods=['GET'])
def get_uploaded_files():
    """Gibt die Liste der hochgeladenen Dateien zurück"""
    session_id = request.args.get('session_id', 'default')
    interview = get_or_create_session(session_id)
    
    # Hole auch RAG-Statistiken
    rag_stats = None
    rag_system = interview.get('rag_system')
    if rag_system:
        rag_stats = rag_system.get_stats()
    
    return jsonify({
        'success': True,
        'files': interview['session_data']['uploaded_files'],
        'rag_stats': rag_stats
    })

@app.route('/api/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Löscht eine hochgeladene Datei"""
    session_id = request.args.get('session_id', 'default')
    interview = get_or_create_session(session_id)
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    
    try:
        # Entferne Datei aus Dateisystem
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"🗑️  Datei gelöscht: {filename}")
        
        # Entferne aus Session
        uploaded_files = interview['session_data']['uploaded_files']
        interview['session_data']['uploaded_files'] = [
            f for f in uploaded_files if f['filename'] != filename
        ]
        
        # Re-initialisiere RAG-System mit verbleibenden Dateien
        remaining_files = interview['session_data']['uploaded_files']
        rag_system = interview.get('rag_system')
        
        if rag_system:
            if remaining_files:
                logger.info(f"🔄 Re-initialisiere RAG-System mit {len(remaining_files)} verbleibenden Dateien...")
                file_paths = [f['filepath'] for f in remaining_files]
                rag_system.initialize(file_paths)
            else:
                logger.info("🔄 Keine Dateien mehr vorhanden, setze RAG-System zurück")
                rag_system.reset()
        
        return jsonify({
            'success': True,
            'message': f'Datei "{filename}" erfolgreich gelöscht',
            'remaining_files': len(remaining_files)
        })
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Löschen von {filename}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Fehler beim Löschen: {str(e)}'
        }), 500

@app.route('/api/rag/stats', methods=['GET'])
def get_rag_stats():
    """Gibt RAG-System Statistiken zurück"""
    session_id = request.args.get('session_id', 'default')
    interview = get_or_create_session(session_id)
    
    rag_system = interview.get('rag_system')
    if rag_system:
        stats = rag_system.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    return jsonify({
        'success': False,
        'message': 'RAG-System nicht verfügbar'
    })


# ==================== LLM Backend API ====================

@app.route('/api/llm/status', methods=['GET'])
def get_llm_status():
    """Gibt den Status aller LLM-Backends zurück"""
    session_id = request.args.get('session_id', 'default')
    interview = get_or_create_session(session_id)
    
    # Hole den MistralClient aus der Engine
    engine = interview['engine']
    llm_client = engine.question_generator.llm
    
    status = llm_client.get_backend_status()
    
    return jsonify({
        'success': True,
        'status': status
    })


@app.route('/api/llm/switch', methods=['POST'])
def switch_llm_backend():
    """Wechselt das LLM-Backend (local oder mistral_api)"""
    data = request.json
    session_id = data.get('session_id', 'default')
    backend = data.get('backend')  # "local" oder "mistral_api"
    
    if not backend:
        return jsonify({
            'success': False,
            'message': 'Kein Backend angegeben'
        }), 400
    
    interview = get_or_create_session(session_id)
    
    # Hole den MistralClient aus der Engine
    engine = interview['engine']
    llm_client = engine.question_generator.llm
    
    # Versuche Backend zu wechseln
    success = llm_client.set_backend(backend)
    
    if success:
        logger.info(f"✅ LLM Backend gewechselt zu: {backend}")
        return jsonify({
            'success': True,
            'message': f'Backend gewechselt zu: {backend}',
            'status': llm_client.get_backend_status()
        })
    else:
        logger.warning(f"⚠️  Backend-Wechsel fehlgeschlagen: {backend}")
        return jsonify({
            'success': False,
            'message': f'Backend-Wechsel fehlgeschlagen. Backend "{backend}" nicht verfügbar.',
            'status': llm_client.get_backend_status()
        }), 400


def get_status_info(session_data, engine=None):
    """Erstellt Status-Informationen für das Frontend inkl. Schema-Fortschritt"""
    phase = session_data.get('phase', PHASE_INTAKE)
    role = session_data.get('role', None)
    
    # Phase-Bezeichnung
    if phase == PHASE_INTAKE:
        phase_label = 'Einstiegsfragen'
    elif phase == PHASE_ROLE:
        phase_label = 'Rollenspezifische Fragen'
    else:
        phase_label = 'Unbekannt'
    
    # Rolle
    role_label = role if role else 'Undefiniert'
    
    # Zusätzliche Infos
    role_confidence_low = session_data.get('role_low_confidence', False)
    
    # Basis-Status
    status = {
        'phase': phase,
        'phase_label': phase_label,
        'role': role,
        'role_label': role_label,
        'role_confidence_low': role_confidence_low,
        'answered_questions': len(session_data.get('answers', {})),
        'uploaded_files_count': len(session_data.get('uploaded_files', []))
    }
    
    # Fortschrittsberechnung
    if phase == PHASE_INTAKE:
        intake_questions = session_data.get('intake_questions', [])
        answered = len([q for q in intake_questions if q.get('id') in session_data.get('answers', {})])
        total = 9  # Feste Anzahl Intake-Fragen
        
        status['progress'] = {
            'current': answered,
            'total': total,
            'percent': round(answered / total * 100, 1) if total > 0 else 0,
            'is_complete': False
        }
    
    elif phase == PHASE_ROLE and role:
        # Schema-basierter Fortschritt
        from interview.role_schema_manager import get_schema_manager
        schema_manager = get_schema_manager()
        
        filled_fields = session_data.get('schema_fields', {})
        progress = schema_manager.calculate_progress(role, filled_fields)
        
        schema = schema_manager.get_schema(role)
        role_name = schema.get('role_name', role) if schema else role
        
        status['role_name'] = role_name
        status['progress'] = {
            'current': progress['filled_required'],
            'total': progress['required_fields'],
            'percent': progress['progress_percent'],
            'is_complete': progress['is_complete'],
            'themes': progress['themes_progress'],
            'missing_required': progress['missing_required']
        }
    
    # Multi-Rollen-Info hinzufügen
    completed_interviews = session_data.get('completed_interviews', [])
    status['completed_interviews'] = len(completed_interviews)
    status['completed_roles'] = [
        {
            'role': i.get('role'),
            'role_label': i.get('role_label'),
            'progress_percent': i.get('progress', {}).get('progress_percent', 0)
        }
        for i in completed_interviews
    ]
    
    return status


@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    """
    Exportiert die Prozessdokumentation als PDF.
    Fasst alle Interviews zusammen und generiert ein professionelles Dokument.
    """
    from doc.pdf_generator import PDFDocumentGenerator
    from datetime import datetime
    
    session_id = request.json.get('session_id', 'default')
    
    # Lade Session-Daten
    interview = get_or_create_session(session_id)
    session_data = interview['session_data']
    
    # Hole abgeschlossene Interviews
    completed_interviews = session_data.get('completed_interviews', [])
    
    # Prüfe ob genug Daten vorhanden
    total_answers = len(session_data.get('answers', {}))
    for ci in completed_interviews:
        total_answers += len(ci.get('answers', {}))
    
    if total_answers == 0:
        return jsonify({
            'success': False,
            'message': 'Keine Interview-Daten vorhanden. Bitte führen Sie zuerst ein Interview durch.'
        }), 400
    
    try:
        # Erstelle PDF-Generator mit Mistral API (beste Ergebnisse)
        mistral_api_key = os.getenv("MISTRAL_API_KEY", "")
        if mistral_api_key:
            logger.info("🔑 PDF-Export: Verwende Mistral API Backend")
            llm_client = MistralClient(backend=BACKEND_MISTRAL_API, api_key=mistral_api_key)
        else:
            logger.warning("⚠️ PDF-Export: Kein MISTRAL_API_KEY - Fallback ohne LLM")
            llm_client = None
        
        pdf_generator = PDFDocumentGenerator(llm_client=llm_client)
        
        # Generiere PDF
        logger.info(f"Generiere PDF für Session {session_id}...")
        pdf_bytes = pdf_generator.generate_pdf(
            session_data=session_data,
            completed_interviews=completed_interviews
        )
        
        # Generiere Dateiname
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Prozessdokumentation_{timestamp}.pdf"
        
        logger.info(f"PDF generiert: {filename} ({len(pdf_bytes)} bytes)")
        
        # Sende PDF als Download
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(pdf_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Fehler bei PDF-Generierung: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Fehler bei der PDF-Generierung: {str(e)}'
        }), 500


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("Interview-Orchestrator Web-Interface")
    print("=" * 70)
    print("\nServer läuft auf: http://localhost:5000")
    print("Drücken Sie STRG+C zum Beenden\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
