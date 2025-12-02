"""
Dynamische Fragengenerierung mit Mistral LLM
Generiert intelligente, kontextbezogene Fragen für die Intake-Phase
und schema-basierte rollenspezifische Fragen.
"""
import json
from typing import Dict, List, Any, Optional, Generator
from app.llm.mistral_client import MistralClient
from interview.role_schema_manager import RoleSchemaManager, get_schema_manager


class DynamicQuestionGenerator:
    """
    Generiert Fragen dynamisch basierend auf vorherigen Antworten.
    Verwendet Mistral LLM für kontextbewusste Fragengenerierung.
    Nutzt rollenspezifische Schemas für strukturierte Interviews.
    """
    
    def __init__(self, llm: MistralClient, schema_manager: RoleSchemaManager = None):
        self.llm = llm
        self.schema_manager = schema_manager or get_schema_manager()
        self.num_initial_questions = 9  # 9 Einstiegsfragen zur Rollendefinition
        self.max_role_questions = 20  # Erhöht: Schema-basierte Fragen können mehr sein
        
        # Vordefiniertes Fragen-Schema für die Intake-Phase
        self.intake_question_schema = [
            {
                "id": "role_function",
                "topic": "Rolle/Funktion",
                "type": "text",
                "hint": "Offene Frage zur Selbstbeschreibung der Position",
                "example": "Welche Rolle bzw. Funktion haben Sie in Ihrem Unternehmen?"
            },
            {
                "id": "tasks_responsibility",
                "topic": "Aufgaben/Verantwortungsbereich",
                "type": "text",
                "hint": "Allgemeine Frage zu täglichen Tätigkeiten",
                "example": "Welche Aufgaben gehören zu Ihrem Verantwortungsbereich?"
            },
            {
                "id": "process_goals",
                "topic": "Ziele im Prozess",
                "type": "text",
                "hint": "Was möchte die Person allgemein erreichen?",
                "example": "Welche Ziele möchten Sie in Ihrem Arbeitsbereich erreichen?"
            },
            {
                "id": "problems_challenges",
                "topic": "Probleme/Herausforderungen",
                "type": "text",
                "hint": "Allgemeine Frage zu Schwierigkeiten im Arbeitsalltag",
                "example": "Welche Herausforderungen begegnen Ihnen typischerweise bei Ihrer Arbeit?"
            },
            {
                "id": "collaboration",
                "topic": "Zusammenarbeit",
                "type": "text",
                "hint": "Mit wem arbeitet die Person zusammen?",
                "example": "Mit welchen Kollegen oder Abteilungen arbeiten Sie regelmäßig zusammen?"
            },
            {
                "id": "success_measurement",
                "topic": "Erfolgsmessung",
                "type": "text",
                "hint": "Wie bewertet die Person ihren Erfolg?",
                "example": "Woran erkennen Sie, dass Sie Ihre Arbeit gut gemacht haben?"
            },
            {
                "id": "operational_decisions",
                "topic": "Operative Entscheidungen",
                "type": "choice",
                "options": ["Ja", "Nein"],
                "hint": "Tagesgeschäft und operative Arbeit",
                "example": "Treffen Sie hauptsächlich operative Entscheidungen im Tagesgeschäft?"
            },
            {
                "id": "technical_responsibility",
                "topic": "Technische Verantwortung",
                "type": "choice",
                "options": ["Ja", "Nein"],
                "hint": "Verantwortung für technische Systeme",
                "example": "Sind Sie für technische Systeme oder deren Betreuung verantwortlich?"
            },
            {
                "id": "project_leadership",
                "topic": "Projektleitung/Teams",
                "type": "choice",
                "options": ["Ja", "Nein"],
                "hint": "Führungsverantwortung",
                "example": "Leiten Sie Projekte oder sind Sie für ein Team verantwortlich?"
            }
        ]
    
    def generate_initial_questions(self, num_questions: int = 9, document_summary: str = "") -> List[Dict[str, Any]]:
        """
        Generiert 9 strukturierte Einstiegsfragen zur Rollendefinition.
        Diese Fragen basieren auf der Ausarbeitung und sind speziell darauf ausgelegt,
        die Rolle (IT, Fach, Management) eindeutig zu identifizieren.
        
        Args:
            num_questions: Anzahl der zu generierenden Fragen (Standard: 9)
            document_summary: Optionale Zusammenfassung der hochgeladenen Dokumente
            
        Returns:
            Liste von 9 Fragen-Dictionaries mit id, text, type, options (bei Multiple Choice)
        """
        # Füge Dokumenten-Zusammenfassung zum System-Prompt hinzu
        summary_addition = ""
        if document_summary:
            summary_addition = f"""
            
            **ZUSAMMENFASSUNG DER UNTERNEHMENSDOKUMENTE:**
            {document_summary}
            
            **Nutze diese Informationen, um die Einstiegsfragen spezifischer auf die Organisation anzupassen.**
            Die Fragen sollten sich auf die konkrete Situation im beschriebenen Unternehmen beziehen.
            Referenziere spezifische Prozesse, Systeme oder Strukturen aus der Zusammenfassung wo sinnvoll.
            """
        
        system_prompt = {
            "role": "system",
            "content": f"""Du bist ein Experte für Prozessanalyse und Organisationspsychologie.
            Deine Aufgabe ist es, 9 strukturierte Einstiegsfragen zu erstellen, die dabei helfen, die Rolle einer Person zu identifizieren.

            **WICHTIG: Die Fragen basieren auf einer wissenschaftlichen Ausarbeitung zur Rollendefinition!**
{summary_addition}
            Die drei Rollen sind:

            **IT-Rolle** (Technische Verantwortliche):
            - Aufgaben: Systemadministration, Schnittstellenbetreuung, Softwareentwicklung
            - Probleme: Systemausfälle, fehlende Schnittstellen
            - Zusammenarbeit: Fachabteilung, andere IT-Mitarbeiter
            - Stärken: Programmierung, Systemvernetzung, Schnittstellenmanagement
            - Erfolgsmessung: Systemstabilität, Anzahl automatisierter Prozesse

            **Fach-Rolle** (Fachabteilung/Sachbearbeiter):
            - Aufgaben: Bearbeitung von Bestellungen, Dokumentenprüfung, operative Prozessarbeit
            - Probleme: Fehler in Dokumenten, Rückfragen, hohe Arbeitslast
            - Zusammenarbeit: IT, Management, Kollegen
            - Stärken: Prozessexperte, Routineaufgaben
            - Erfolgsmessung: Bearbeitungszeit, Fehlerquote
            - Trifft hauptsächlich operative Entscheidungen

            **Management-Rolle** (Führungskräfte):
            - Aufgaben: Strategische Planung, Projektleitung, Budgetverantwortung
            - Probleme: Verzögerungen, fehlende Transparenz
            - Zusammenarbeit: Geschäftsführung, Projektleiter
            - Stärken: Stratege, Führungsexpertise, Finanzexperte
            - Erfolgsmessung: Kostenreduktion, Prozessdurchlaufzeit
            - Leitet Projekte oder Teams

            **Die 9 Fragen MÜSSEN in dieser Reihenfolge abdecken:**
            1. **Rolle/Funktion** - OFFEN (kein Multiple Choice!), damit die Person ihre Rolle selbst beschreibt
            2. **Aufgaben/Verantwortungsbereich** - Offen, um rollenspezifische Aufgaben zu identifizieren
            3. **Ziele im Prozess** - Was möchte die Person erreichen? (technisch/operativ/strategisch)
            4. **Probleme/Herausforderungen** - Welche typischen Probleme treten auf?
            5. **Zusammenarbeit** - Mit welchen Rollen arbeitet die Person zusammen?
            6. **Erfolgsmessung** - Woran misst die Person Erfolg?
            7. **Operative Entscheidungen** - Ja/Nein Frage (Ja → Fachabteilung)
            8. **Technische Verantwortung** - Ja/Nein Frage (Ja → IT)
            9. **Projektleitung/Teams** - Ja/Nein Frage (Ja → Management)

            **Für die erste Frage verwende:**
            - Frage 1: type="text" (NICHT choice!), offen formuliert

            **Für Multiple-Choice-Fragen verwende:**
            - Fragen 7-9: type="choice", options=["Ja", "Nein"]

            **Für offene Fragen verwende:**
            - Fragen 2-6: type="text"

            Antworte AUSSCHLIESSLICH im folgenden JSON-Format:
            {{
            "questions": [
                {{
                "id": "role_function",
                "text": "Welche Rolle bzw. Funktion haben Sie in Ihrem Unternehmen?",
                "type": "text",
                "required": true
                }},
                {{
                "id": "eindeutige_id",
                "text": "Die Frage selbst",
                "type": "text|choice",
                "options": ["Option1", "Option2"],
                "required": true
                }}
            ]
            }}

            WICHTIG: Generiere GENAU 9 Fragen in der oben beschriebenen Reihenfolge!
            """
        }
        
        user_prompt = {
            "role": "user",
            "content": f"""Generiere GENAU {num_questions} strukturierte Einstiegsfragen zur Rollendefinition.

            Die Fragen MÜSSEN genau diesem Schema folgen:
            1. Rolle/Funktion (OFFEN - keine Auswahloptionen!)
            2. Aufgaben/Verantwortungsbereich (Offen)
            3. Ziele im Prozess (Offen)
            4. Probleme/Herausforderungen (Offen)
            5. Zusammenarbeit mit anderen Rollen (Offen)
            6. Erfolgsmessung (Offen)
            7. Treffen Sie hauptsächlich operative Entscheidungen? (Ja/Nein)
            8. Sind Sie verantwortlich für technische Systeme oder Software? (Ja/Nein)
            9. Leiten Sie Projekte oder Teams? (Ja/Nein)

            Diese Fragen basieren auf einer wissenschaftlichen Ausarbeitung und sind optimal für die Rollenzuordnung.

            Antworte mit genau {num_questions} Fragen im JSON-Format."""
        }
        
        try:
            response = self.llm.complete(
                messages=[system_prompt, user_prompt],
                json_mode={"type": "json_object"},
            )
            
            result = self._parse_response(response.choices[0].message.content)
            questions = result.get("questions", [])
            
            # Stelle sicher, dass genau num_questions Fragen zurückgegeben werden
            if len(questions) != num_questions:
                print(f"⚠️  LLM generierte {len(questions)} statt {num_questions} Fragen, verwende Fallback")
                return self._get_fallback_questions()
            
            # Validiere und normalisiere
            return self._validate_questions(questions)
            
        except Exception as e:
            print(f"⚠️  Fehler bei Fragengenerierung: {e}")
            # Fallback: Verwende Basis-Fragen
            return self._get_fallback_questions()
    
    def generate_single_intake_question(
        self,
        question_index: int,
        answers: Dict[str, str],
        previous_questions: List[Dict[str, Any]],
        document_summary: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Generiert eine einzelne Intake-Frage dynamisch basierend auf vorherigen Antworten.
        
        Args:
            question_index: Index der zu generierenden Frage (0-8)
            answers: Bisherige Antworten
            previous_questions: Bereits gestellte Fragen
            document_summary: Optionale Zusammenfassung der hochgeladenen Dokumente
            
        Returns:
            Einzelne Frage als Dictionary oder None bei Fehler
        """
        if question_index >= len(self.intake_question_schema):
            return None
        
        schema = self.intake_question_schema[question_index]
        
        # Kontext aus vorherigen Antworten aufbauen
        context_parts = []
        for i, q in enumerate(previous_questions):
            q_id = q.get("id", "")
            answer = answers.get(q_id, "")
            if answer:
                context_parts.append(f"Frage {i+1} ({q.get('topic', '')}): {q.get('text', '')}\nAntwort: {answer}")
        
        previous_context = "\n\n".join(context_parts) if context_parts else "Noch keine Antworten vorhanden."
        
        # Dokumenten-Kontext hinzufügen
        doc_context = ""
        if document_summary:
            doc_context = f"""

**KONTEXT AUS UNTERNEHMENSDOKUMENTEN:**
{document_summary}

Beziehe dich auf spezifische Aspekte aus den Dokumenten, wenn passend.
"""
        
        system_prompt = {
            "role": "system",
            "content": f"""Du führst ein Interview zur Prozessdokumentation. Formuliere eine offene, neutrale Frage.

Du generierst jetzt Frage Nr. {question_index + 1} von 9 Einstiegsfragen.

**THEMA DIESER FRAGE:** {schema['topic']}
**FRAGETYP:** {schema['type']}
**BEISPIELFORMULIERUNG:** "{schema['example']}"
{doc_context}

**WICHTIGE REGELN:**
1. Formuliere die Frage OFFEN und NEUTRAL - keine Suggestionen oder Annahmen
2. Passe die Formulierung natürlich an den bisherigen Gesprächsverlauf an
3. Wenn in den Antworten spezifische Details genannt wurden, beziehe dich darauf
4. Vermeide kategorisierende Begriffe wie "IT", "Fachabteilung", "Management"
5. Die Frage soll zum Erzählen einladen, nicht zu einer bestimmten Antwort führen
6. Für type="choice": Verwende genau die vorgegebenen Optionen

**BISHERIGER INTERVIEW-VERLAUF:**
{previous_context}

Antworte AUSSCHLIESSLICH im JSON-Format:
{{
    "id": "{schema['id']}",
    "text": "Deine formulierte Frage - offen und neutral",
    "type": "{schema['type']}",
    {"'options': " + json.dumps(schema.get('options', [])) + "," if schema['type'] == 'choice' else ""}
    "required": true
}}"""
        }
        
        user_prompt = {
            "role": "user",
            "content": f"Formuliere eine offene, neutrale Frage zum Thema '{schema['topic']}' basierend auf dem bisherigen Gesprächsverlauf."
        }
        
        try:
            response = self.llm.complete(
                messages=[system_prompt, user_prompt],
                json_mode={"type": "json_object"},
                temperature=0.7
            )
            
            result = self._parse_response(response.choices[0].message.content)
            
            # Validiere und ergänze Felder
            result["id"] = schema["id"]
            result["type"] = schema["type"]
            result["required"] = True
            if schema["type"] == "choice":
                result["options"] = schema.get("options", ["Ja", "Nein"])
            
            validated = self._validate_questions([result])
            return validated[0] if validated else self._get_fallback_questions()[question_index]
            
        except Exception as e:
            print(f"⚠️  Fehler bei Einzelfragen-Generierung: {e}")
            return self._get_fallback_questions()[question_index]
    
    def generate_single_intake_question_stream(
        self,
        question_index: int,
        answers: Dict[str, str],
        previous_questions: List[Dict[str, Any]],
        document_summary: str = ""
    ) -> Generator[str, None, Optional[Dict[str, Any]]]:
        """
        Generiert eine einzelne Intake-Frage mit Streaming.
        Yielded Text-Chunks während der Generierung.
        Gibt am Ende die vollständige Frage als Dictionary zurück.
        
        Args:
            question_index: Index der zu generierenden Frage (0-8)
            answers: Bisherige Antworten
            previous_questions: Bereits gestellte Fragen
            document_summary: Optionale Zusammenfassung
            
        Yields:
            Text-Chunks während der Generierung
            
        Returns:
            Fertige Frage als Dictionary (über generator.send() oder als letzter yield)
        """
        if question_index >= len(self.intake_question_schema):
            return None
        
        schema = self.intake_question_schema[question_index]
        
        # Kontext aus vorherigen Antworten
        context_parts = []
        for i, q in enumerate(previous_questions):
            q_id = q.get("id", "")
            answer = answers.get(q_id, "")
            if answer:
                context_parts.append(f"Frage {i+1}: {q.get('text', '')[:100]}\nAntwort: {answer[:200]}")
        
        previous_context = "\n".join(context_parts[-3:]) if context_parts else "Noch keine Antworten."
        
        doc_hint = ""
        if document_summary:
            doc_hint = f"\n\nKontext aus Dokumenten: {document_summary[:500]}..."
        
        system_prompt = {
            "role": "system",
            "content": f"""Du führst ein Interview zur Prozessdokumentation. Formuliere eine offene, neutrale Frage.

Frage {question_index + 1}/9 - Thema: "{schema['topic']}"
Beispielformulierung: "{schema['example']}"
Fragetyp: {schema['type']}
{doc_hint}

**WICHTIGE REGELN:**
1. Formuliere die Frage OFFEN und NEUTRAL - vermeide Suggestionen oder Annahmen
2. Passe die Formulierung natürlich an den bisherigen Gesprächsverlauf an
3. Beziehe dich auf konkrete Details aus vorherigen Antworten, falls passend
4. Vermeide Fachbegriffe wie "IT-Rolle", "Fachabteilung", "Management" in der Frage
5. Die Frage soll zum Erzählen einladen, nicht kategorisieren

Gib NUR den Fragetext aus, ohne JSON oder Formatierung."""
        }
        
        user_prompt = {
            "role": "user",
            "content": f"""Bisheriger Gesprächsverlauf:
{previous_context}

Formuliere eine offene, neutrale Frage zum Thema "{schema['topic']}":"""
        }
        
        full_text = ""
        
        try:
            for chunk in self.llm.complete_stream(
                messages=[system_prompt, user_prompt],
                temperature=0.7
            ):
                if chunk.content:
                    full_text += chunk.content
                    yield chunk.content
                if chunk.done:
                    break
            
            # Bereinige den Text
            question_text = full_text.strip().strip('"').strip()
            
            # Erstelle finales Question-Dictionary
            result = {
                "id": schema["id"],
                "text": question_text,
                "type": schema["type"],
                "required": True
            }
            
            if schema["type"] == "choice":
                result["options"] = schema.get("options", ["Ja", "Nein"])
            
            # Speichere das Ergebnis für den Aufrufer
            yield {"__complete__": True, "question": result}
            
        except Exception as e:
            print(f"⚠️  Fehler bei Streaming-Generierung: {e}")
            fallback = self._get_fallback_questions()[question_index]
            yield {"__complete__": True, "question": fallback}
    
    def generate_role_specific_question(
        self,
        role: str,
        answers: Dict[str, str],
        previous_questions: List[Dict[str, Any]],
        question_number: int,
        document_context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Generiert eine rollenspezifische Folgefrage.
        Diese Fragen sind auf die identifizierte Rolle zugeschnitten.
        
        Args:
            role: Die identifizierte Rolle (it, fach, management)
            answers: Bisherige Antworten
            previous_questions: Bereits gestellte rollenspezifische Fragen
            question_number: Nummer der rollenspezifischen Frage
            document_context: Optionaler Kontext aus hochgeladenen Dokumenten
            
        Returns:
            Frage-Dictionary oder None wenn keine weitere Frage nötig
        """
        # Stoppe nach max_role_questions
        if len(previous_questions) >= self.max_role_questions:
            return None
        
        # Rollenbeschreibungen für den Kontext
        role_descriptions = {
            "it": "IT-Verantwortliche/r (technische Infrastruktur, APIs, Schnittstellen, Sicherheit)",
            "fach": "Fachabteilung/Sachbearbeiter/in (Geschäftsprozesse, Workflows, manuelle Tätigkeiten)",
            "management": "Führungskraft/Manager/in (Strategie, KPIs, ROI, Risikomanagement)"
        }
        
        # Themen-Katalog für jede Rolle (wird rotiert, nicht repetiert)
        role_topics = {
            "it": [
                "System-Architektur und Schnittstellen",
                "Authentifizierung und Zugriffskontrolle",
                "Deployment und Release-Prozesse",
                "Monitoring und Fehlerbehandlung",
                "Datenformate und Protokolle",
                "Performance und Skalierung"
            ],
            "fach": [
                "Geschäftsregeln und Validierung",
                "Manuelle Arbeitsschritte im Prozess",
                "Ausnahmen und Sonderfälle",
                "Qualitätsanforderungen",
                "Durchlaufzeiten und Engpässe",
                "Stakeholder und Genehmigungen"
            ],
            "management": [
                "Business-Value und Erfolgsmetriken",
                "Risiken und Compliance",
                "Budget und Ressourcen",
                "Strategische Ziele",
                "Stakeholder-Erwartungen",
                "Change Management"
            ]
        }
        
        # Wähle nächstes unbehandeltes Thema
        topics = role_topics.get(role, [])
        current_topic_index = (question_number - 1) % len(topics) if topics else 0
        current_topic = topics[current_topic_index] if topics else "Allgemein"
        
        # Füge Dokumentenkontext hinzu falls verfügbar
        context_addition = ""
        if document_context:
            context_addition = f"""

**RELEVANTER KONTEXT AUS DOKUMENTEN:**
{document_context}

**Berücksichtige diesen Kontext bei der Formulierung deiner Frage.**
Stelle Fragen, die helfen, die dokumentierten Prozesse und die Rolle der Person darin besser zu verstehen.
"""
        
        system_prompt = {
            "role": "system",
            "content": f"""Du bist ein Experte für Prozessanalyse und führst ein strukturiertes Interview mit einer Person aus der Rolle: {role_descriptions.get(role, role)}.
{context_addition}
**WICHTIGE REGELN:**
1. Stelle BREITE Fragen zu verschiedenen Themen, nicht tiefe Nachfragen zum selben Detail
2. Wenn eine Antwort vage ist ("weiß ich nicht", "kann ich nichts zu sagen"), wechsle das Thema
3. Decke verschiedene Aspekte der Rolle ab, nicht nur einen
4. Halte Fragen auf einem mittleren Detaillevel - nicht zu oberflächlich, nicht zu technisch
5. Akzeptiere ungefähre Antworten und gehe zum nächsten Thema über

**AKTUELLES THEMA:** {current_topic}

**Deine Frage soll:**
- Zum aktuellen Thema "{current_topic}" passen
- Für Prozessdokumentation relevante Informationen sammeln
- Verständlich und nicht zu spezifisch sein
- Bei vagen Antworten NICHT nachbohren, sondern Thema wechseln

Antworte AUSSCHLIESSLICH im folgenden JSON-Format:
{{
  "question": {{
    "id": "role_{role}_q{question_number}",
    "text": "Die Frage zum Thema {current_topic}",
    "type": "text",
    "required": true,
    "hint": "Optional: Hilfetext"
  }},
  "reasoning": "Warum diese Information für die Dokumentation wichtig ist"
}}

Wenn alle Themen abgedeckt wurden, antworte:
{{
  "question": null,
  "reasoning": "Alle wichtigen Aspekte wurden abgedeckt"
}}
"""
        }
        
        # Bereite kompakten Kontext auf mit Fokus auf letzte Interaktion
        answered_count = len(answers)
        last_answer = list(answers.values())[-1] if answers else "Noch keine Antwort"
        
        # Erstelle Kontext aus vorherigen Fragen und Antworten für besseres Follow-up
        conversation_context = ""
        if previous_questions:
            # Zeige die letzten 2 Fragen und Antworten für Kontext
            recent_qa = []
            for q in previous_questions[-2:]:
                q_id = q.get('id')
                q_text = q.get('text', '')
                answer = answers.get(q_id, 'Keine Antwort')
                recent_qa.append(f"F: {q_text}\nA: {answer[:150]}...")
            
            if recent_qa:
                conversation_context = "\n\n**Bisherige Fragen & Antworten:**\n" + "\n\n".join(recent_qa)
        
        user_prompt = {
            "role": "user",
            "content": f"""Bisheriger Interview-Verlauf:
- Anzahl beantworteter Fragen: {answered_count}
- Letzte Antwort: "{last_answer[:200]}..."
{conversation_context}

**Stelle jetzt eine Frage zum Thema: {current_topic}**

Dies ist Frage #{question_number} für die Rolle {role}.

**WICHTIG:** 
- Berücksichtige die letzte Antwort, um spezifischer nachzufragen
- Wenn die letzte Antwort interessante Details enthält, frage tiefer nach
- Wenn die Antwort vage war, stelle eine konkretere Frage
- Nutze den Dokumenten-Kontext für präzisere Fragen

Antworte im JSON-Format."""
        }
        
        try:
            response = self.llm.complete(
                messages=[system_prompt, user_prompt],
                json_mode={"type": "json_object"},
            )
            
            result = self._parse_response(response.choices[0].message.content)
            question = result.get("question")
            
            if question is None:
                return None
            
            # Validiere Frage
            validated = self._validate_questions([question])
            return validated[0] if validated else None
            
        except Exception as e:
            print(f"⚠️  Fehler bei rollenspezifischer Fragengenerierung: {e}")
            return None
    
    def generate_schema_based_question(
        self,
        role: str,
        filled_fields: Dict[str, Any],
        answers: Dict[str, str],
        document_context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Generiert eine Frage basierend auf dem rollenspezifischen Schema.
        Nutzt die JSON-Schemas aus role_schema_*.json.
        
        Args:
            role: Die identifizierte Rolle (it, fach, management)
            filled_fields: Dictionary mit bereits ausgefüllten Schema-Feldern
            answers: Bisherige Antworten (für Kontext)
            document_context: Optionaler Kontext aus hochgeladenen Dokumenten
            
        Returns:
            Frage-Dictionary oder None wenn alle Felder ausgefüllt sind
        """
        # Hole das nächste unbeantwortete Feld aus dem Schema
        next_field = self.schema_manager.get_next_unanswered_field(role, filled_fields)
        
        if next_field is None:
            # Alle Pflichtfelder sind ausgefüllt
            print(f"✅ Alle Schema-Felder für Rolle '{role}' ausgefüllt")
            return None
        
        field_id, field_def = next_field
        
        # Baue Kontext aus vorherigen Antworten
        context_parts = []
        recent_answers = list(answers.items())[-3:]  # Letzte 3 Antworten
        for q_id, answer in recent_answers:
            if answer:
                context_parts.append(f"- {q_id}: {answer[:150]}...")
        previous_context = "\n".join(context_parts) if context_parts else "Noch keine Antworten."
        
        # Dokumentenkontext
        doc_context = ""
        if document_context:
            doc_context = f"""

**KONTEXT AUS DOKUMENTEN:**
{document_context[:500]}
"""
        
        # Typ-spezifische Instruktionen
        type_instruction = self._get_type_instruction(field_def)
        
        system_prompt = {
            "role": "system",
            "content": f"""Du führst ein strukturiertes Interview für die Rolle: {self.schema_manager.get_schema(role).get('role_name', role)}.

**AKTUELLES THEMENFELD:** {field_def.get('theme_name', 'Allgemein')}
**FELD-ID:** {field_id}
**ORIGINAL-FRAGE:** {field_def.get('question', '')}
**HINWEIS:** {field_def.get('hint', '')}
{doc_context}

**DEINE AUFGABE:**
Formuliere die Frage natürlich und passend zum bisherigen Gesprächsverlauf.
Die Frage soll die gleichen Informationen erfassen wie die Original-Frage,
aber flüssiger und kontextbezogener formuliert sein.

{type_instruction}

**WICHTIG:**
1. Behalte den Informationsgehalt der Original-Frage bei
2. Passe die Formulierung an den bisherigen Dialog an
3. Sei freundlich aber professionell
4. Vermeide zu technische Sprache wo möglich

Antworte im JSON-Format:
{{
    "text": "Die formulierte Frage",
    "follow_up_hint": "Optionaler Hinweis für Nachfragen"
}}"""
        }
        
        user_prompt = {
            "role": "user",
            "content": f"""Bisheriger Kontext:
{previous_context}

Formuliere nun eine natürliche Frage für das Feld '{field_id}' im Themenfeld '{field_def.get('theme_name', 'Allgemein')}'."""
        }
        
        try:
            response = self.llm.complete(
                messages=[system_prompt, user_prompt],
                json_mode={"type": "json_object"},
                temperature=0.7
            )
            
            result = self._parse_response(response.choices[0].message.content)
            question_text = result.get("text", field_def.get("question", ""))
            
            # Erstelle das Fragen-Dictionary
            question = {
                "id": f"schema_{field_id}",
                "field_id": field_id,
                "text": question_text,
                "type": field_def.get("type", "text"),
                "required": field_def.get("required", True),
                "theme_id": field_def.get("theme_id"),
                "theme_name": field_def.get("theme_name"),
                "hint": field_def.get("hint", ""),
                "original_question": field_def.get("question", "")
            }
            
            # Füge typ-spezifische Felder hinzu
            if field_def.get("type") == "choice":
                question["options"] = field_def.get("options", [])
            elif field_def.get("type") == "multiple_choice":
                question["options"] = field_def.get("options", [])
                question["multiple"] = True
            elif field_def.get("type") == "scale":
                question["scale_min"] = field_def.get("scale_min", 1)
                question["scale_max"] = field_def.get("scale_max", 5)
                question["scale_labels"] = field_def.get("scale_labels", {})
            elif field_def.get("type") == "ranking":
                question["options"] = field_def.get("options", [])
                question["ranking"] = True
            elif field_def.get("type") == "number":
                question["unit"] = field_def.get("unit", "")
            
            return question
            
        except Exception as e:
            print(f"⚠️  Fehler bei Schema-basierter Fragengenerierung: {e}")
            # Fallback: Verwende Original-Frage direkt
            return {
                "id": f"schema_{field_id}",
                "field_id": field_id,
                "text": field_def.get("question", f"Bitte beantworten Sie die Frage zu {field_id}"),
                "type": field_def.get("type", "text"),
                "required": field_def.get("required", True),
                "theme_id": field_def.get("theme_id"),
                "theme_name": field_def.get("theme_name"),
                "options": field_def.get("options", []) if field_def.get("type") in ["choice", "multiple_choice", "ranking"] else None
            }
    
    def _get_type_instruction(self, field_def: Dict[str, Any]) -> str:
        """Gibt typ-spezifische Instruktionen für die Frageformulierung."""
        field_type = field_def.get("type", "text")
        
        if field_type == "choice":
            options = field_def.get("options", [])
            return f"**FRAGETYP:** Auswahloptionen - Die Antwort sollte eine der folgenden sein: {', '.join(options)}"
        
        elif field_type == "multiple_choice":
            options = field_def.get("options", [])
            return f"**FRAGETYP:** Mehrfachauswahl - Mehrere der folgenden Optionen können gewählt werden: {', '.join(options)}"
        
        elif field_type == "scale":
            scale_min = field_def.get("scale_min", 1)
            scale_max = field_def.get("scale_max", 5)
            labels = field_def.get("scale_labels", {})
            return f"**FRAGETYP:** Skala von {scale_min} bis {scale_max} ({labels.get(str(scale_min), '')} bis {labels.get(str(scale_max), '')})"
        
        elif field_type == "number":
            unit = field_def.get("unit", "")
            return f"**FRAGETYP:** Zahleneingabe (Einheit: {unit})"
        
        elif field_type == "ranking":
            options = field_def.get("options", [])
            return f"**FRAGETYP:** Rangfolge - Diese Optionen sollen priorisiert werden: {', '.join(options)}"
        
        elif field_type == "text_list":
            return "**FRAGETYP:** Liste/Aufzählung - Mehrere Elemente als Antwort erwartet"
        
        elif field_type == "text_with_frequency":
            return "**FRAGETYP:** Text mit Häufigkeitsangabe - Elemente mit Häufigkeit (täglich/wöchentlich/selten)"
        
        return "**FRAGETYP:** Offene Textantwort"
    
    def get_role_progress(self, role: str, filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gibt den Fortschritt für eine Rolle zurück.
        Wrapper für schema_manager.calculate_progress.
        """
        return self.schema_manager.calculate_progress(role, filled_fields)
    
    def get_progress_display(self, role: str, filled_fields: Dict[str, Any]) -> str:
        """
        Gibt eine formatierte Fortschrittsanzeige zurück.
        Wrapper für schema_manager.get_progress_display.
        """
        return self.schema_manager.get_progress_display(role, filled_fields)
    
    def is_interview_complete(self, role: str, filled_fields: Dict[str, Any]) -> bool:
        """Prüft ob das Interview für eine Rolle abgeschlossen ist."""
        progress = self.schema_manager.calculate_progress(role, filled_fields)
        return progress.get("is_complete", False)
    
    def extract_fields_from_answer(
        self,
        role: str,
        answer: str,
        current_field_id: str,
        filled_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extrahiert Feldwerte aus einer Antwort.
        Eine umfangreiche Antwort kann mehrere Felder füllen.
        
        Args:
            role: Die aktuelle Rolle
            answer: Die Antwort des Nutzers
            current_field_id: Das Feld für das die Frage gestellt wurde
            filled_fields: Bereits ausgefüllte Felder
            
        Returns:
            Dictionary mit extrahierten Feldwerten
        """
        updates = {current_field_id: answer}
        
        # Hole alle noch offenen Felder
        all_fields = self.schema_manager.get_all_fields(role)
        open_fields = {
            fid: fdef for fid, fdef in all_fields.items()
            if fid not in filled_fields and fid != current_field_id
        }
        
        if not open_fields or len(answer) < 100:
            # Kurze Antworten oder keine offenen Felder: nur Hauptfeld
            return updates
        
        # Versuche zusätzliche Felder zu extrahieren via LLM
        # (nur bei umfangreichen Antworten)
        fields_info = "\n".join([
            f"- {fid}: {fdef.get('question', '')} (Typ: {fdef.get('type', 'text')})"
            for fid, fdef in list(open_fields.items())[:5]  # Max 5 Felder prüfen
        ])
        
        system_prompt = {
            "role": "system",
            "content": f"""Analysiere die Antwort und prüfe, ob sie Informationen zu mehreren Feldern enthält.

**OFFENE FELDER:**
{fields_info}

**AUFGABE:**
Prüfe ob die Antwort Informationen enthält, die eines der offenen Felder beantworten könnten.
Extrahiere NUR klar erkennbare Informationen, rate nicht.

Antworte im JSON-Format:
{{
    "extracted_fields": {{
        "field_id": "extrahierter Wert",
        ...
    }},
    "confidence": "high|medium|low"
}}

Bei geringer Konfidenz oder unklaren Informationen: leeres extracted_fields zurückgeben."""
        }
        
        try:
            response = self.llm.complete(
                messages=[
                    system_prompt,
                    {"role": "user", "content": f"Antwort des Nutzers:\n{answer}"}
                ],
                json_mode={"type": "json_object"},
                temperature=0.3
            )
            
            result = self._parse_response(response.choices[0].message.content)
            
            if result.get("confidence") in ["high", "medium"]:
                extracted = result.get("extracted_fields", {})
                for field_id, value in extracted.items():
                    if field_id in open_fields and value:
                        updates[field_id] = value
                        print(f"📝 Zusätzliches Feld extrahiert: {field_id}")
            
        except Exception as e:
            print(f"⚠️  Fehler bei Feldextraktion: {e}")
        
        return updates
    
    def _format_interview_context(
        self, 
        answers: Dict[str, str], 
        questions: List[Dict[str, Any]]
    ) -> str:
        """Formatiert den Interview-Kontext für das LLM"""
        context_parts = []
        
        context_parts.append(f"Bisher wurden {len(questions)} Fragen gestellt:\n")
        
        for i, q in enumerate(questions, 1):
            q_id = q.get("id", "unknown")
            q_text = q.get("text", "")
            answer = answers.get(q_id, "[Keine Antwort]")
            
            context_parts.append(f"{i}. Frage: {q_text}")
            context_parts.append(f"   Antwort: {answer}\n")
        
        return "\n".join(context_parts)
    
    def _parse_response(self, payload: str) -> Dict[str, Any]:
        """Parst die LLM-Antwort"""
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            # Versuche JSON aus Text zu extrahieren
            import re
            m = re.search(r"\{.*\}", payload, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise ValueError(f"Konnte JSON nicht parsen: {payload}")
    
    def _validate_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validiert und normalisiert Fragen"""
        validated = []
        
        for q in questions:
            if not isinstance(q, dict):
                continue
            
            # Erforderliche Felder
            if "id" not in q or "text" not in q:
                continue
            
            # Normalisiere ID (keine Leerzeichen, lowercase)
            q["id"] = q["id"].replace(" ", "_").lower()
            
            # Setze Defaults
            if "type" not in q:
                q["type"] = "text"
            
            if "required" not in q:
                q["required"] = True
            
            validated.append(q)
        
        return validated
    
    def _get_fallback_questions(self) -> List[Dict[str, Any]]:
        """Fallback-Fragen basierend auf der wissenschaftlichen Ausarbeitung"""
        return [
            {
                "id": "role_function",
                "text": "Welche Rolle bzw. Funktion haben Sie in Ihrem Unternehmen?",
                "type": "text",
                "required": True,
                "hint": "Beschreiben Sie Ihre Position oder Funktion"
            },
            {
                "id": "tasks_responsibility",
                "text": "Welche Aufgaben gehören zu Ihrem Verantwortungsbereich?",
                "type": "text",
                "required": True,
                "hint": "Beschreiben Sie Ihre typischen Tätigkeiten"
            },
            {
                "id": "process_goals",
                "text": "Welche Ziele möchten Sie in diesem Prozess erreichen?",
                "type": "text",
                "required": True,
                "hint": "Was soll verbessert oder erreicht werden?"
            },
            {
                "id": "problems_challenges",
                "text": "Welche Probleme oder Herausforderungen treten typischerweise bei Ihrer Arbeit auf?",
                "type": "text",
                "required": True
            },
            {
                "id": "collaboration",
                "text": "Mit welchen Rollen oder Personen arbeiten Sie regelmäßig zusammen?",
                "type": "text",
                "required": True
            },
            {
                "id": "success_measurement",
                "text": "Woran messen Sie Erfolg in diesem Prozess?",
                "type": "text",
                "required": True,
                "hint": "Welche Metriken oder Kennzahlen sind wichtig?"
            },
            {
                "id": "operational_decisions",
                "text": "Treffen Sie hauptsächlich operative Entscheidungen?",
                "type": "choice",
                "options": ["Ja", "Nein"],
                "required": True
            },
            {
                "id": "technical_responsibility",
                "text": "Sind Sie verantwortlich für technische Systeme oder Software?",
                "type": "choice",
                "options": ["Ja", "Nein"],
                "required": True
            },
            {
                "id": "project_leadership",
                "text": "Leiten Sie Projekte oder Teams?",
                "type": "choice",
                "options": ["Ja", "Nein"],
                "required": True
            }
        ]
