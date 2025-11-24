"""
Intelligenter Fragebogen - KI-Assistent zur Informationsaufnahme und Prozessdokumentation
Chat-Interface für interaktive Befragung
"""
import os
import sys
from dotenv import load_dotenv
from app.llm.mistral_client import MistralClient
from interview.repo import QuestionRepo
from interview.role_classifier import RoleClassifier
from interview.question_generator import DynamicQuestionGenerator
from interview.engine import InterviewEngine, PHASE_INTAKE, PHASE_ROLE
from doc.generator import DocGenerator

load_dotenv()

def print_header():
    """Zeigt den Willkommens-Header"""
    print("\n" + "=" * 70)
    print("🤖 Intelligenter Fragebogen - KI-Assistent")
    print("   Informationsaufnahme und Prozessdokumentation")
    print("=" * 70)
    print("\nWillkommen! Ich helfe Ihnen dabei, Ihre Geschäftsprozesse zu")
    print("dokumentieren. Bitte beantworten Sie die folgenden Fragen.")
    print("\nTipps:")
    print("  • Geben Sie 'exit' oder 'quit' ein, um das Interview zu beenden")
    print("  • Geben Sie 'status' ein, um den aktuellen Stand zu sehen")
    print("  • Geben Sie 'dokument' ein, um die Dokumentation zu generieren")
    print("=" * 70 + "\n")

def print_question(question, question_num, total_questions=None):
    """Formatiert und zeigt eine Frage an"""
    prefix = f"\n📋 Frage {question_num}" + (f" von ~{total_questions}" if total_questions else "")
    print("\n" + "-" * 70)
    print(f"{prefix}")
    print(f"❓ {question['text']}")
    
    if question.get('type') == 'choice' and question.get('options'):
        print("\nOptionen:")
        for i, option in enumerate(question['options'], 1):
            print(f"  {i}. {option}")
    print("-" * 70)

def get_user_input(question):
    """Holt die Benutzereingabe und validiert sie"""
    while True:
        user_input = input("\n💬 Ihre Antwort: ").strip()
        
        # Spezielle Kommandos
        if user_input.lower() in ['exit', 'quit', 'beenden']:
            return None
        if user_input.lower() == 'status':
            return 'STATUS'
        if user_input.lower() == 'dokument':
            return 'DOKUMENT'
        
        # Validierung für Multiple Choice
        if question.get('type') == 'choice':
            options = question.get('options', [])
            # Prüfe ob Nummer eingegeben wurde
            if user_input.isdigit():
                num = int(user_input)
                if 1 <= num <= len(options):
                    return options[num - 1]
                else:
                    print(f"❌ Bitte wählen Sie eine Zahl zwischen 1 und {len(options)}")
                    continue
            # Prüfe ob Text eingegeben wurde der einer Option entspricht
            for option in options:
                if user_input.lower() == option.lower():
                    return option
            print(f"❌ Bitte wählen Sie eine der angegebenen Optionen (1-{len(options)}) oder geben Sie den Text ein")
            continue
        
        # Für Textfragen: Leere Antworten nicht erlauben
        if not user_input:
            print("❌ Bitte geben Sie eine Antwort ein")
            continue
            
        return user_input

def show_status(session):
    """Zeigt den aktuellen Status des Interviews"""
    print("\n" + "=" * 70)
    print("📊 Status")
    print("=" * 70)
    print(f"Phase: {session['phase']}")
    print(f"Rolle: {session.get('role', 'Noch nicht bestimmt')}")
    print(f"Beantwortete Fragen: {len(session['answers'])}")
    
    if session.get('role_candidates'):
        print(f"\nRollen-Kandidaten:")
        for candidate in session['role_candidates'][:3]:
            print(f"  • {candidate['role']}: {candidate['score']:.2%} Übereinstimmung")
    
    if session.get('role_low_confidence'):
        print("\n⚠️  Die Rollenzuordnung ist unsicher, es werden zusätzliche Fragen gestellt")
    print("=" * 70)

def generate_document(session, doc_generator):
    """Generiert und zeigt die Dokumentation"""
    answers = session.get('answers', {})
    questions = session.get('questions', [])
    role = session.get('role', 'it')
    
    print("\n" + "=" * 70)
    print("📄 Generiere Dokumentation mit KI-Analyse...")
    print("=" * 70)
    
    try:
        # Dokumentation mit LLM generieren
        document = doc_generator.render_it(questions, answers)
        
        print("\n" + "=" * 70)
        print("📝 PROZESSDOKUMENTATION")
        print("=" * 70)
        print(document)
        print("=" * 70)
        
        # Optional: Dokumentation speichern
        save = input("\n💾 Möchten Sie die Dokumentation speichern? (j/n): ").strip().lower()
        if save in ['j', 'ja', 'y', 'yes']:
            filename = f"prozessdokumentation_{role}_{session['session_id'][:8]}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(document)
            print(f"✅ Dokumentation gespeichert in: {filename}")
    
    except Exception as e:
        print(f"❌ Fehler beim Generieren der Dokumentation: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Hauptfunktion für das Chat-Interface"""
    # Initialisierung
    repo = QuestionRepo(path=os.path.join(os.path.dirname(__file__), "config", "questions.json"))
    llm = MistralClient()
    classifier = RoleClassifier(llm)
    question_generator = DynamicQuestionGenerator(llm)
    engine = InterviewEngine(
        repo=repo,
        classifier=classifier,
        question_generator=question_generator,
        use_dynamic_questions=True  # Aktiviere dynamische Fragen
    )
    doc_generator = DocGenerator(llm)
    
    # Session erstellen
    import uuid
    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "phase": PHASE_INTAKE,
        "role": None,
        "answers": {},
        "questions": [],  # Speichert alle gestellten Fragen
        "role_candidates": []
    }
    
    # Willkommens-Header
    print_header()
    
    question_count = 0
    
    # Interview-Loop
    while True:
        # Nächste Frage holen
        question = engine.next_question(session)
        
        if question is None:
            print("\n" + "=" * 70)
            print("✅ Interview abgeschlossen!")
            print("=" * 70)
            print(f"\nSie haben alle Fragen beantwortet ({len(session['answers'])} Antworten).")
            print(f"Ihre Rolle wurde identifiziert als: {session.get('role', 'Unbekannt')}")
            
            # Automatisch Dokumentation generieren
            print("\n🔄 Generiere finale Dokumentation...")
            generate_document(session, doc_generator)
            break
        
        question_count += 1
        
        # Frage anzeigen
        print_question(question, question_count)
        
        # Frage in Session speichern
        session["questions"].append(question)
        
        # Antwort holen
        answer = get_user_input(question)
        
        # Spezielle Kommandos
        if answer is None:
            print("\n👋 Interview abgebrochen. Auf Wiedersehen!")
            break
        elif answer == 'STATUS':
            show_status(session)
            question_count -= 1  # Zähler nicht erhöhen
            continue
        elif answer == 'DOKUMENT':
            generate_document(session, doc_generator)
            question_count -= 1  # Zähler nicht erhöhen
            continue
        
        # Antwort speichern
        session["answers"][question["id"]] = answer
        print(f"✓ Antwort gespeichert")
        
        # Discriminator: Option → Rolle setzen
        for d in repo.discriminators():
            if d["id"] == question["id"]:
                opt_map = d.get("options_to_role", {})
                mapped_role = opt_map.get(str(answer), "")
                if mapped_role:
                    session["role"] = mapped_role
                    session["phase"] = PHASE_ROLE
                    print(f"\n🎯 Rolle identifiziert: {mapped_role}")
                    print("   Die folgenden Fragen sind spezifisch für Ihre Rolle.")
    
    print("\n" + "=" * 70)
    print("Vielen Dank für Ihre Teilnahme!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interview durch Benutzer unterbrochen. Auf Wiedersehen!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ein Fehler ist aufgetreten: {e}")
        sys.exit(1)
