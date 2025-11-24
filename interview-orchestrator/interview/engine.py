from typing import Dict, Any, Optional, List
from interview.repo import QuestionRepo
from interview.role_classifier import RoleClassifier
from interview.question_generator import DynamicQuestionGenerator

PHASE_INTAKE = "intake"
PHASE_ROLE = "role_specific"

class InterviewEngine:
    def __init__(
        self, 
        repo: QuestionRepo, 
        classifier: RoleClassifier,
        question_generator: Optional[DynamicQuestionGenerator] = None,
        use_dynamic_questions: bool = True,
        demo_mode: bool = False
    ):
        self.repo = repo
        self.classifier = classifier
        self.question_generator = question_generator
        self.use_dynamic_questions = use_dynamic_questions and question_generator is not None
        self.demo_mode = demo_mode

    def _unanswered(self, questions, answers):
        for q in questions:
            if q["id"] not in answers:
                return q
        return None

    def next_question(self, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        phase = session.get("phase", PHASE_INTAKE)
        answers = session.setdefault("answers", {})
        role = session.get("role")

        # Phase 0: Universal Intake (jetzt dynamisch mit LLM)
        if phase == PHASE_INTAKE:
            if self.use_dynamic_questions:
                intake_question = self._next_dynamic_intake_question(session)
                if intake_question:
                    # Es gibt noch eine Intake-Frage zu stellen
                    return intake_question
                # Alle Intake-Fragen beantwortet → Führe Rollenklassifikation durch
            else:
                # Fallback: Statische Fragen aus JSON
                q = self._unanswered(self.repo.universal(), answers)
                if q:
                    return q

            # Intake fertig → Rollenklassifikation
            print(f"\n{'='*70}")
            print("🎯 Starte Rollenklassifikation")
            print(f"{'='*70}")
            print(f"📊 Anzahl Antworten: {len(answers)}")
            
            result = self.classifier.classify(answers)
            
            print(f"\n📋 Klassifikationsergebnis:")
            print(f"   Quelle: {result.get('source', 'unknown')}")
            print(f"   Kandidaten: {result.get('candidates', [])}")
            
            session["role_candidates"] = result.get("candidates", [])
            session["classification_explanation"] = result.get("explain", "")
            
            top = session["role_candidates"][0] if session["role_candidates"] else None
            
            print(f"\n🔍 Top-Kandidat: {top}")
            print(f"   Score-Threshold: 0.7")
            
            if top and top["score"] >= 0.7:
                session["role"] = top["role"]
                session["phase"] = PHASE_ROLE
                print(f"\n✅ Rolle identifiziert: {top['role']} (Konfidenz: {top['score']:.0%})")
                if session.get("classification_explanation"):
                    print(f"   Begründung: {session['classification_explanation']}")
            else:
                print(f"\n⚠️  Rolle unsicher (Score: {top['score'] if top else 0:.0%} < 70%)")
                
                # Bei unsicherer Zuordnung: Generiere zusätzliche klärende Fragen
                if self.use_dynamic_questions and self.question_generator:
                    clarifying_questions = session.setdefault("clarifying_questions", [])
                    
                    # Maximal 3 zusätzliche Klärungsfragen
                    if len(clarifying_questions) < 3:
                        print("   → Generiere zusätzliche Klärungsfrage...")
                        clarifying_q = self._generate_clarifying_question(session, top)
                        if clarifying_q:
                            clarifying_questions.append(clarifying_q)
                            session["clarifying_questions"] = clarifying_questions
                            return clarifying_q
                
                # Fallback: Discriminator-Fragen aus JSON (falls vorhanden)
                dq = self._unanswered(self.repo.discriminators(), answers)
                if dq:
                    print("   → Stelle zusätzliche Discriminator-Frage...")
                    return dq
                
                # Wenn immer noch unklar: Übernehme Top-Kandidat mit niedrigerer Konfidenz
                if top:
                    session["role"] = top["role"]
                    session["role_low_confidence"] = True
                    session["phase"] = PHASE_ROLE
                    print(f"\n🤔 Rolle unsicher identifiziert: {top['role']} (Konfidenz: {top['score']:.0%})")
                else:
                    print(f"\n❌ FEHLER: Kein Kandidat verfügbar!")
                    print(f"   Klassifikationsergebnis: {result}")
                    # Setze Fallback-Rolle
                    session["role"] = "fach"
                    session["role_low_confidence"] = True
                    session["phase"] = PHASE_ROLE
                    print(f"   → Verwende Fallback-Rolle: fach")
            
            print(f"{'='*70}\n")
            
            # Im Demo-Modus: Beende Interview nach Rollenklassifikation
            if self.demo_mode:
                print("\n🎬 DEMO-MODUS: Interview endet nach Rollenklassifikation\n")
                return None
            
            # Rekursiver Aufruf um die erste rollenspezifische Frage zu holen
            return self.next_question(session)

        # Phase 1: rollenspezifische Fragen (jetzt auch dynamisch mit LLM)
        if session.get("phase") == PHASE_ROLE and session.get("role"):
            if self.use_dynamic_questions:
                return self._next_dynamic_role_question(session)
            else:
                # Fallback: Statische Fragen aus JSON
                rq = self._unanswered(self.repo.by_role(session["role"]), answers)
                if rq:
                    return rq
            return None  # fertig

        return None
    
    def _next_dynamic_intake_question(self, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generiert genau 9 allgemeine Intake-Fragen dynamisch mit LLM.
        Nach diesen 9 Fragen erfolgt die Rollenklassifikation.
        """
        answers = session.get("answers", {})
        asked_questions = session.setdefault("intake_questions", [])
        
        # Erste 9 Fragen generieren (falls noch keine gestellt wurden)
        if not asked_questions:
            print("\n🤖 Generiere 9 allgemeine Einstiegsfragen mit KI...")
            initial_questions = self.question_generator.generate_initial_questions(num_questions=9)
            print(f"✅ {len(initial_questions)} Fragen generiert")
            session["intake_questions"] = initial_questions
            asked_questions = initial_questions
            print(f"📝 Session intake_questions gesetzt: {len(session.get('intake_questions', []))} Fragen")
            
            if asked_questions:
                return asked_questions[0]
        
        # Prüfe ob es noch unbeantwortete Fragen gibt
        unanswered = self._unanswered(asked_questions, answers)
        if unanswered:
            return unanswered
        
        # Alle 9 Fragen beantwortet → Intake-Phase ist abgeschlossen
        print(f"\n✅ Alle {len(asked_questions)} allgemeinen Fragen beantwortet")
        return None
    
    def _next_dynamic_role_question(self, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generiert rollenspezifische Folgefragen dynamisch mit LLM.
        """
        answers = session.get("answers", {})
        role = session.get("role")
        role_questions = session.setdefault("role_questions", [])
        
        # Prüfe ob es noch unbeantwortete rollenspezifische Fragen gibt
        unanswered = self._unanswered(role_questions, answers)
        if unanswered:
            return unanswered
        
        # Generiere nächste rollenspezifische Frage
        question_number = len(role_questions) + 1
        
        # Maximal max_role_questions
        if question_number > self.question_generator.max_role_questions:
            print(f"\n✅ Rollenspezifische Phase abgeschlossen ({len(role_questions)} Fragen für Rolle '{role}')")
            return None
        
        print(f"\n🤖 Generiere rollenspezifische Frage #{question_number} für Rolle '{role}'...")
        role_question = self.question_generator.generate_role_specific_question(
            role=role,
            answers=answers,
            previous_questions=role_questions,
            question_number=question_number
        )
        
        if role_question:
            role_questions.append(role_question)
            session["role_questions"] = role_questions
            return role_question
        
        # Keine weitere Frage nötig
        print(f"\n✅ Rollenspezifische Phase abgeschlossen ({len(role_questions)} Fragen für Rolle '{role}')")
        return None
    
    def _generate_clarifying_question(self, session: Dict[str, Any], top_candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generiert eine Klärungsfrage bei unsicherer Rollenzuordnung.
        Diese Fragen helfen, zwischen ähnlichen Rollen zu unterscheiden.
        """
        if not self.question_generator:
            return None
        
        answers = session.get("answers", {})
        candidates = session.get("role_candidates", [])
        
        # Identifiziere die zwei wahrscheinlichsten Rollen
        top_two = candidates[:2] if len(candidates) >= 2 else candidates
        
        clarifying_questions_count = len(session.get("clarifying_questions", []))
        
        # Generiere spezifische Frage zur Unterscheidung
        question_id = f"clarifying_{clarifying_questions_count + 1}"
        
        # Einfache Klärungsfragen basierend auf den Kandidaten
        if len(top_two) >= 2:
            role1, role2 = top_two[0]["role"], top_two[1]["role"]
            
            clarifying_map = {
                ("it", "fach"): {
                    "text": "Arbeiten Sie mehr mit technischen Systemen und deren Integration oder mit fachlichen Prozessen und deren Bearbeitung?",
                    "type": "choice",
                    "options": ["Technische Systeme", "Fachliche Prozesse"]
                },
                ("it", "management"): {
                    "text": "Liegt Ihr Fokus eher auf der technischen Umsetzung oder auf strategischen Entscheidungen und Führung?",
                    "type": "choice",
                    "options": ["Technische Umsetzung", "Strategie und Führung"]
                },
                ("fach", "management"): {
                    "text": "Beschäftigen Sie sich hauptsächlich mit der operativen Durchführung von Aufgaben oder mit der strategischen Planung und Steuerung?",
                    "type": "choice",
                    "options": ["Operative Durchführung", "Strategische Planung"]
                }
            }
            
            key = (role1, role2) if (role1, role2) in clarifying_map else (role2, role1)
            if key in clarifying_map:
                question_data = clarifying_map[key]
                return {
                    "id": question_id,
                    "text": question_data["text"],
                    "type": question_data["type"],
                    "options": question_data.get("options", []),
                    "required": True
                }
        
        return None
    
    def process_answer(self, answer: str) -> Optional[Dict[str, Any]]:
        """Verarbeitet eine Antwort und gibt die nächste Frage zurück"""
        if not self.current_question:
            return None
        
        # Speichere die Antwort
        self.answers[self.current_question.id] = answer
        
        # Prüfe, ob wir genug Antworten für Rollenklassifikation haben
        # Geändert: Erst nach ALLEN 9 Einstiegsfragen klassifizieren
        if self.phase == "entry" and len(self.answers) >= 9:
            print(f"\n✅ Alle 9 Einstiegsfragen beantwortet. Starte Rollenklassifikation...")
            
            # Klassifiziere die Rolle
            classification = self.classifier.classify(self.answers)
            self.role_classification = classification
            
            print(f"🎯 Rollenklassifikation abgeschlossen: {classification}")
            
            # Prüfe die Confidence des Top-Kandidaten
            if classification and classification.get("candidates"):
                top_candidate = classification["candidates"][0]
                confidence = top_candidate.get("score", 0)
                
                print(f"📊 Top-Kandidat: {top_candidate['role']} mit {confidence*100}% Confidence")
                
                # Demo-Modus: Beende nach Klassifikation
                if self.demo_mode:
                    print("🎬 Demo-Modus: Interview endet nach Rollenklassifikation")
                    self.current_question = None
                    return None
                
                # Wenn Confidence hoch genug, wechsle zu rollenspezifischen Fragen
                if confidence >= self.confidence_threshold:
                    self.phase = "role_specific"
                    self.assigned_role = top_candidate["role"]
                    print(f"✅ Rolle '{self.assigned_role}' mit hoher Confidence zugewiesen")
                    return self._generate_next_role_question()
                else:
                    # Niedrige Confidence: Stelle Klärungsfragen
                    print(f"⚠️  Niedrige Confidence ({confidence*100}%). Stelle Klärungsfragen...")
                    self.phase = "clarification"
                    return self._generate_clarification_question(classification)
        
        # Generiere die nächste Frage
        return self._generate_next_question()
