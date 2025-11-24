"""
Flask-Webanwendung für das Interview-System
Leichtgewichtige Web-UI mit Streaming, Reset-Funktion, Status-Anzeige und Dokument-Upload
Inkl. RAG-System für kontextbasierte Fragen aus hochgeladenen Dokumenten
"""
import os
import json
import logging
from flask import Flask, render_template, request, jsonify, Response, session as flask_session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from threading import Lock
from app.llm.mistral_client import MistralClient
from interview.repo import QuestionRepo
from interview.role_classifier import RoleClassifier
from interview.question_generator import DynamicQuestionGenerator
from interview.engine import InterviewEngine, PHASE_INTAKE, PHASE_ROLE
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

def get_or_create_session(session_id):
    """Holt oder erstellt eine Interview-Session (thread-safe)"""
    with session_lock:
        if session_id not in interview_sessions:
            logger.info(f"🆕 Erstelle NEUE Session: {session_id}")
            # Initialisiere Interview-Komponenten
            llm_client = MistralClient()
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
            
            interview_sessions[session_id] = {
                'engine': engine,
                'doc_generator': DocGenerator(llm_client),
                'rag_system': rag_system,
                'session_data': {
                    'phase': PHASE_INTAKE,
                    'answers': {},
                    'role': None,
                    'intake_questions': [],
                    'role_questions': [],
                    'uploaded_files': existing_files
                }
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

@app.route('/')
def index():
    """Hauptseite"""
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_interview():
    """Startet ein neues Interview"""
    session_id = request.json.get('session_id', 'default')
    print(f"\n🚀 /api/start aufgerufen für Session: {session_id}")
    interview = get_or_create_session(session_id)
    
    # Setze Prozess-Status
    interview['session_data']['process_status'] = 'Generiere Einstiegsfragen mit KI...'
    
    # Hole die erste Frage
    question = interview['engine'].next_question(interview['session_data'])
    
    print(f"📊 Nach next_question: intake_questions = {len(interview['session_data'].get('intake_questions', []))}")
    
    # Lösche Prozess-Status
    interview['session_data']['process_status'] = None
    
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

@app.route('/api/reset', methods=['POST'])
def reset_interview():
    """Setzt das Interview zurück"""
    session_id = request.json.get('session_id', 'default')
    
    # Lösche die Session
    if session_id in interview_sessions:
        del interview_sessions[session_id]
    
    # Erstelle neue Session und hole erste Frage
    interview = get_or_create_session(session_id)
    question = interview['engine'].next_question(interview['session_data'])
    
    return jsonify({
        'success': True,
        'message': 'Interview wurde zurückgesetzt',
        'question': question,
        'status': get_status_info(interview['session_data'])
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

def get_status_info(session_data):
    """Erstellt Status-Informationen für das Frontend"""
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
    
    return {
        'phase': phase,
        'phase_label': phase_label,
        'role': role,
        'role_label': role_label,
        'role_confidence_low': role_confidence_low,
        'answered_questions': len(session_data.get('answers', {})),
        'uploaded_files_count': len(session_data.get('uploaded_files', []))
    }

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("Interview-Orchestrator Web-Interface")
    print("=" * 70)
    print("\nServer läuft auf: http://localhost:5000")
    print("Drücken Sie STRG+C zum Beenden\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
