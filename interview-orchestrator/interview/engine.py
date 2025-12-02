from typing import Dict, Any, Optional, List
from interview.repo import QuestionRepo
from interview.role_classifier import RoleClassifier
from interview.question_generator import DynamicQuestionGenerator
from interview.role_schema_manager import RoleSchemaManager, get_schema_manager

PHASE_INTAKE = "intake"
PHASE_ROLE = "role_specific"

class InterviewEngine:
    def __init__(
        self, 
        repo: QuestionRepo, 
        classifier: RoleClassifier,
        question_generator: Optional[DynamicQuestionGenerator] = None,
        use_dynamic_questions: bool = True,
        demo_mode: bool = False,
        rag_system = None,
        schema_manager: Optional[RoleSchemaManager] = None
    ):
        self.repo = repo
        self.classifier = classifier
        self.question_generator = question_generator
        self.use_dynamic_questions = use_dynamic_questions and question_generator is not None
        self.demo_mode = demo_mode
        self.rag_system = rag_system  # RAG-System für kontextbasierte Fragen
        self.schema_manager = schema_manager or get_schema_manager()

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
        Generiert Intake-Fragen dynamisch einzeln mit LLM.
        Jede Frage wird basierend auf den vorherigen Antworten angepasst.
        """
        answers = session.get("answers", {})
        asked_questions = session.setdefault("intake_questions", [])
        
        # Berechne wie viele Fragen bereits beantwortet wurden
        answered_count = len([q for q in asked_questions if q.get("id") in answers])
        
        # Prüfe ob es noch eine unbeantwortete Frage gibt
        unanswered = self._unanswered(asked_questions, answers)
        if unanswered:
            return unanswered
        
        # Alle bisherigen Fragen beantwortet - generiere nächste Frage
        next_index = len(asked_questions)
        
        # Maximal 9 Intake-Fragen
        if next_index >= 9:
            print(f"\n✅ Alle {len(asked_questions)} allgemeinen Fragen beantwortet")
            return None
        
        print(f"\n🤖 Generiere Intake-Frage #{next_index + 1} dynamisch mit KI...")
        
        # Intake-Fragen werden OHNE Dokumenten-Kontext generiert
        # um neutrale, allgemeine Fragen zu stellen
        question = self.question_generator.generate_single_intake_question(
            question_index=next_index,
            answers=answers,
            previous_questions=asked_questions,
            document_summary=""  # Kein Dokumenten-Kontext für Intake
        )
        
        if question:
            asked_questions.append(question)
            session["intake_questions"] = asked_questions
            print(f"✅ Frage #{next_index + 1} generiert: {question.get('text', '')[:50]}...")
            return question
        
        # Fallback: Alle Fragen beantwortet
        print(f"\n✅ Alle {len(asked_questions)} allgemeinen Fragen beantwortet")
        return None
    
    def next_question_stream(self, session: Dict[str, Any]):
        """
        Generator-Variante von next_question für Streaming.
        Yielded Text-Chunks während der Fragen-Generierung.
        
        Yields:
            Entweder Text-Chunks (str) oder das finale Ergebnis (dict mit 'question' key)
        """
        phase = session.get("phase", PHASE_INTAKE)
        answers = session.setdefault("answers", {})
        
        # Phase 0: Universal Intake mit Streaming
        if phase == PHASE_INTAKE:
            if self.use_dynamic_questions:
                # Prüfe ob es noch eine unbeantwortete Frage gibt
                asked_questions = session.get("intake_questions", [])
                unanswered = self._unanswered(asked_questions, answers)
                if unanswered:
                    yield {"question": unanswered, "done": True}
                    return
                
                next_index = len(asked_questions)
                
                # Alle 9 Fragen beantwortet?
                if next_index >= 9:
                    # Rollenklassifikation durchführen (kein Streaming nötig)
                    yield {"status": "Analysiere Antworten und klassifiziere Rolle..."}
                    result = self._perform_role_classification(session)
                    yield result
                    return
                
                # Generiere nächste Frage mit Streaming
                yield {"status": f"Generiere Frage {next_index + 1}/9..."}
                
                # Hole Dokument-Zusammenfassung
                asked_questions = session.setdefault("intake_questions", [])
                
                # Intake-Fragen werden OHNE Dokumenten-Kontext generiert (Streaming)
                # um neutrale, allgemeine Fragen zu stellen
                for chunk in self.question_generator.generate_single_intake_question_stream(
                    question_index=next_index,
                    answers=answers,
                    previous_questions=asked_questions,
                    document_summary=""  # Kein Dokumenten-Kontext für Intake
                ):
                    if isinstance(chunk, dict) and chunk.get("__complete__"):
                        question = chunk.get("question")
                        if question:
                            asked_questions.append(question)
                            session["intake_questions"] = asked_questions
                        yield {"question": question, "done": True}
                        return
                    else:
                        yield {"chunk": chunk}
                
                return
            else:
                # Fallback: Statische Fragen
                q = self._unanswered(self.repo.universal(), answers)
                if q:
                    yield {"question": q, "done": True}
                    return
                
                # Rollenklassifikation
                result = self._perform_role_classification(session)
                yield result
                return
        
        # Phase 1: Rollenspezifische Fragen
        if session.get("phase") == PHASE_ROLE and session.get("role"):
            if self.use_dynamic_questions:
                question = self._next_dynamic_role_question(session)
                yield {"question": question, "done": True}
            else:
                rq = self._unanswered(self.repo.by_role(session["role"]), answers)
                yield {"question": rq, "done": True}
            return
        
        yield {"question": None, "done": True}
    
    def _perform_role_classification(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Führt die Rollenklassifikation durch und gibt das Ergebnis zurück.
        """
        answers = session.get("answers", {})
        
        print(f"\n{'='*70}")
        print("🎯 Starte Rollenklassifikation")
        print(f"{'='*70}")
        
        result = self.classifier.classify(answers)
        
        session["role_candidates"] = result.get("candidates", [])
        session["classification_explanation"] = result.get("explain", "")
        
        top = session["role_candidates"][0] if session["role_candidates"] else None
        
        if top and top["score"] >= 0.7:
            session["role"] = top["role"]
            session["phase"] = PHASE_ROLE
            print(f"\n✅ Rolle identifiziert: {top['role']} (Konfidenz: {top['score']:.0%})")
        else:
            if top:
                session["role"] = top["role"]
                session["role_low_confidence"] = True
                session["phase"] = PHASE_ROLE
                print(f"\n🤔 Rolle unsicher identifiziert: {top['role']} (Konfidenz: {top['score']:.0%})")
            else:
                session["role"] = "fach"
                session["role_low_confidence"] = True
                session["phase"] = PHASE_ROLE
        
        if self.demo_mode:
            print("\n🎬 DEMO-MODUS: Interview endet nach Rollenklassifikation\n")
            return {"question": None, "done": True, "role_classified": True}
        
        # Hole erste rollenspezifische Frage
        if self.use_dynamic_questions:
            question = self._next_dynamic_role_question(session)
        else:
            question = self._unanswered(self.repo.by_role(session["role"]), answers)
        
        return {"question": question, "done": True, "role_classified": True}
    
    def _next_dynamic_role_question(self, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generiert rollenspezifische Folgefragen basierend auf dem Schema.
        Nutzt die JSON-Schemas für strukturierte, vollständige Interviews.
        """
        answers = session.get("answers", {})
        role = session.get("role")
        role_questions = session.setdefault("role_questions", [])
        filled_fields = session.setdefault("schema_fields", {})
        
        # Prüfe ob es noch unbeantwortete rollenspezifische Fragen gibt
        unanswered = self._unanswered(role_questions, answers)
        if unanswered:
            return unanswered
        
        # Berechne und zeige Fortschritt
        progress = self.schema_manager.calculate_progress(role, filled_fields)
        
        # Zeige Fortschritt im Log
        print(f"\n📊 Schema-Fortschritt für '{role}':")
        print(f"   Ausgefüllt: {progress['filled_fields']}/{progress['total_fields']} ({progress['progress_percent']}%)")
        print(f"   Pflichtfelder: {progress['filled_required']}/{progress['required_fields']}")
        
        # Prüfe ob Interview abgeschlossen ist
        if progress["is_complete"]:
            print(f"\n🎉 Interview für Rolle '{role}' vollständig abgeschlossen!")
            print(self.schema_manager.get_progress_display(role, filled_fields))
            return None
        
        # Generiere nächste Frage basierend auf Schema
        question_number = len(role_questions) + 1
        
        # Sicherheitscheck: Maximale Fragenanzahl
        if question_number > self.question_generator.max_role_questions:
            print(f"\n⚠️  Maximale Fragenanzahl erreicht ({question_number})")
            print(f"   Noch fehlende Felder: {progress['missing_required']}")
            return None
        
        print(f"\n🤖 Generiere schema-basierte Frage #{question_number} für Rolle '{role}'...")
        
        # RAG-Kontext ist OPTIONAL und wird nur für spezifische technische Themen geholt
        # um die Fragen nicht zu stark durch Dokumenten-Inhalte zu beeinflussen
        rag_context = ""
        next_field = self.schema_manager.get_next_unanswered_field(role, filled_fields)
        
        # Schlüsselwörter für Themen, bei denen RAG-Kontext sinnvoll ist
        # (technische Details, Systeminfos, Datenmanagement, Automatisierung)
        rag_keywords = ["systemlandschaft", "datenmanagement", "automatisierung", "schnittstellen", 
                        "architektur", "technical", "system", "integration", "security", "compliance"]
        
        if next_field and self.rag_system and self.rag_system.is_initialized:
            field_id, field_def = next_field
            theme_id = field_def.get("theme_id", "").lower()
            hint = field_def.get("hint", "").lower()
            
            # RAG nur für technische/spezifische Themen verwenden
            # Prüfe ob Theme-ID oder Hint eines der RAG-relevanten Schlüsselwörter enthält
            use_rag_for_field = any(kw in theme_id or kw in hint for kw in rag_keywords)
            
            if use_rag_for_field:
                query_parts = [
                    role, 
                    field_def.get("theme_name", ""),
                    field_def.get("question", "")[:100]
                ]
                role_query = " ".join(query_parts)
                print(f"📚 Hole RAG-Kontext für technisches Thema: {field_def.get('theme_name', 'Allgemein')}")
                rag_context = self.rag_system.get_context_for_question(role_query)
            else:
                print(f"ℹ️  Kein RAG-Kontext für Thema '{field_def.get('theme_name', '')}' (Interview-basiert)")
        
        # Generiere Frage basierend auf Schema
        role_question = self.question_generator.generate_schema_based_question(
            role=role,
            filled_fields=filled_fields,
            answers=answers,
            document_context=rag_context
        )
        
        if role_question:
            role_questions.append(role_question)
            session["role_questions"] = role_questions
            
            # Zeige aktuelles Themenfeld
            theme_name = role_question.get("theme_name", "Allgemein")
            print(f"   Themenfeld: {theme_name}")
            print(f"   Feld: {role_question.get('field_id', 'unknown')}")
            
            return role_question
        
        # Keine weitere Frage nötig
        print(f"\n✅ Rollenspezifische Phase abgeschlossen ({len(role_questions)} Fragen für Rolle '{role}')")
        print(self.schema_manager.get_progress_display(role, filled_fields))
        return None
    
    def process_role_answer(
        self, 
        session: Dict[str, Any], 
        question: Dict[str, Any], 
        answer: str
    ) -> Dict[str, Any]:
        """
        Verarbeitet eine Antwort auf eine rollenspezifische Frage.
        Extrahiert Feldwerte und aktualisiert den Fortschritt.
        
        Args:
            session: Die aktuelle Session
            question: Die beantwortete Frage
            answer: Die Antwort des Nutzers
            
        Returns:
            Dictionary mit Fortschritts-Informationen
        """
        role = session.get("role")
        answers = session.setdefault("answers", {})
        filled_fields = session.setdefault("schema_fields", {})
        
        # Speichere Antwort
        question_id = question.get("id")
        answers[question_id] = answer
        
        # Extrahiere Feldwerte
        field_id = question.get("field_id")
        if field_id:
            # Versuche zusätzliche Felder zu extrahieren
            extracted = self.question_generator.extract_fields_from_answer(
                role=role,
                answer=answer,
                current_field_id=field_id,
                filled_fields=filled_fields
            )
            
            # Aktualisiere filled_fields
            for fid, value in extracted.items():
                filled_fields[fid] = value
                print(f"✅ Feld '{fid}' ausgefüllt")
            
            session["schema_fields"] = filled_fields
        
        # Berechne neuen Fortschritt
        progress = self.schema_manager.calculate_progress(role, filled_fields)
        
        return {
            "progress": progress,
            "filled_fields_count": len(filled_fields),
            "is_complete": progress["is_complete"],
            "progress_percent": progress["progress_percent"]
        }
    
    def get_interview_progress(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gibt den aktuellen Interview-Fortschritt zurück.
        
        Returns:
            Dictionary mit Fortschritts-Informationen für die UI
        """
        phase = session.get("phase", PHASE_INTAKE)
        role = session.get("role")
        
        if phase == PHASE_INTAKE:
            # Intake-Phase: Zähle Fragen
            intake_questions = session.get("intake_questions", [])
            answered = len([q for q in intake_questions if q.get("id") in session.get("answers", {})])
            total = 9  # Feste Anzahl Intake-Fragen
            
            return {
                "phase": "intake",
                "phase_name": "Einstiegsfragen",
                "current": answered,
                "total": total,
                "progress_percent": round(answered / total * 100, 1) if total > 0 else 0,
                "is_complete": False,
                "role": None
            }
        
        elif phase == PHASE_ROLE and role:
            # Rollenspezifische Phase: Nutze Schema-Fortschritt
            filled_fields = session.get("schema_fields", {})
            progress = self.schema_manager.calculate_progress(role, filled_fields)
            
            schema = self.schema_manager.get_schema(role)
            role_name = schema.get("role_name", role) if schema else role
            
            return {
                "phase": "role_specific",
                "phase_name": f"Rollenspezifische Fragen ({role_name})",
                "current": progress["filled_required"],
                "total": progress["required_fields"],
                "progress_percent": progress["progress_percent"],
                "is_complete": progress["is_complete"],
                "role": role,
                "role_name": role_name,
                "themes_progress": progress["themes_progress"],
                "missing_required": progress["missing_required"]
            }
        
        return {
            "phase": "unknown",
            "phase_name": "Unbekannt",
            "current": 0,
            "total": 0,
            "progress_percent": 0,
            "is_complete": False,
            "role": None
        }
    
    def get_filled_schema(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gibt das ausgefüllte Schema für die aktuelle Rolle zurück.
        Nützlich für Export und Dokumentation.
        """
        role = session.get("role")
        filled_fields = session.get("schema_fields", {})
        
        if not role:
            return {}
        
        schema = self.schema_manager.get_schema(role)
        if not schema:
            return {}
        
        # Erstelle strukturiertes Ergebnis
        result = {
            "role": role,
            "role_name": schema.get("role_name", role),
            "completed_at": None,  # Kann später mit Timestamp gefüllt werden
            "themes": {}
        }
        
        for theme_id, theme_data in schema.get("fields", {}).items():
            theme_result = {
                "name": theme_data.get("name", theme_id),
                "fields": {}
            }
            
            for field_id, field_def in theme_data.get("fields", {}).items():
                theme_result["fields"][field_id] = {
                    "question": field_def.get("question", ""),
                    "value": filled_fields.get(field_id, None),
                    "type": field_def.get("type", "text"),
                    "required": field_def.get("required", False),
                    "is_filled": field_id in filled_fields
                }
            
            result["themes"][theme_id] = theme_result
        
        return result
    
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
