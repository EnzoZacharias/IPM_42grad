"""
Dynamische Fragengenerierung mit Mistral LLM
Generiert intelligente, kontextbezogene Fragen für die Intake-Phase
"""
import json
from typing import Dict, List, Any, Optional
from app.llm.mistral_client import MistralClient


class DynamicQuestionGenerator:
    """
    Generiert Fragen dynamisch basierend auf vorherigen Antworten.
    Verwendet Mistral LLM für kontextbewusste Fragengenerierung.
    """
    
    def __init__(self, llm: MistralClient):
        self.llm = llm
        self.num_initial_questions = 9  # 9 Einstiegsfragen zur Rollendefinition
        self.max_role_questions = 10  # Maximal 10 rollenspezifische Fragen
    
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
