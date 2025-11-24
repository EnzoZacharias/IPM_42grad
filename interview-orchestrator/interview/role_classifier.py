import re
import json
from typing import Dict, Any, List
from app.llm.mistral_client import MistralClient

class RoleClassifier:
    """
    KI-gestützte Rollenklassifikation mit Mistral LLM.
    Klassifiziert Benutzer anhand ihrer Antworten in:
    - IT: Technische Verantwortliche, Entwickler, System-Administratoren
    - Fach: Fachabteilung, Sachbearbeiter, Prozessverantwortliche
    - Management: Führungskräfte, Entscheidungsträger
    """
    
    def __init__(self, llm: MistralClient, threshold: float = 0.6):
        self.llm = llm
        self.threshold = threshold

    def classify(self, answers: Dict[str, str]) -> Dict[str, Any]:
        """
        Klassifiziert die Rolle des Benutzers basierend auf seinen Antworten.
        Verwendet Mistral LLM für intelligente Analyse.
        
        Args:
            answers: Dictionary mit Frage-IDs und Antworten
            
        Returns:
            Dictionary mit candidates (Liste von {role, score}) und optional explain
        """
        # System-Prompt für die Rollenklassifikation
        system = {
            "role": "system",
            "content": """Du bist ein Experte für Organisationsanalyse und Prozessmanagement.
            Deine Aufgabe ist es, basierend auf den Antworten einer Person deren Rolle in einem Automatisierungsprojekt zu identifizieren.

            Es gibt drei mögliche Rollen:

            1. **it** - IT/Technische Verantwortliche:
            - Typische Rollenbezeichnungen: IT-Administrator, Softwareentwickler, System-Administrator, DevOps, IT-Architekt
            - Aufgaben: Systemadministration, Schnittstellenbetreuung, Softwareentwicklung, Server-Verwaltung
            - Typische Probleme: Systemausfälle, fehlende Schnittstellen, Performance-Probleme, Security-Issues
            - Zusammenarbeit: Fachabteilung, andere IT-Mitarbeiter, externe Dienstleister
            - Berufliche Stärken: Programmierung, Systemvernetzung, Schnittstellenmanagement, technische Problemlösung
            - Erfolgsmessung: Systemstabilität, Verfügbarkeit, Anzahl automatisierter Prozesse, Performance-Metriken
            - Ziele: Systeme stabil halten, Integration sichern, Automatisierung vorantreiben
            - Verantwortlich für technische Systeme oder Software: **JA**
            - Trifft hauptsächlich operative Entscheidungen: NEIN (technische Entscheidungen)
            - Leitet Projekte oder Teams: Möglich, aber nicht primär

            2. **fach** - Fachabteilung/Sachbearbeiter:
            - Typische Rollenbezeichnungen: Sachbearbeiter, Fachexperte, Prozessverantwortlicher, Teamleiter Fachbereich
            - Aufgaben: Bearbeitung von Bestellungen, Dokumentenprüfung, operative Prozessarbeit, Kundenbetreuung
            - Typische Probleme: Fehler in Dokumenten, Rückfragen, hohe Arbeitslast, manuelle Prozesse
            - Zusammenarbeit: IT, Management, Kollegen, Kunden
            - Berufliche Stärken: Prozessexperte, Routineaufgaben, Fachkenntnisse, Detailgenauigkeit
            - Erfolgsmessung: Bearbeitungszeit, Fehlerquote, Durchlaufzeit, Kundenzufriedenheit
            - Ziele: Fehlerreduktion, Zeiteinsparung, Prozessoptimierung
            - Verantwortlich für technische Systeme oder Software: **NEIN**
            - Trifft hauptsächlich operative Entscheidungen: **JA**
            - Leitet Projekte oder Teams: **NEIN** (außer kleine Fach-Teams)

            3. **management** - Führungskräfte/Management:
            - Typische Rollenbezeichnungen: Abteilungsleiter, Projektleiter, Manager, Geschäftsführer, Team Lead
            - Aufgaben: Strategische Planung, Projektleitung, Budgetverantwortung, Teamführung
            - Typische Probleme: Verzögerungen, fehlende Transparenz, Ressourcenengpässe, Kommunikation
            - Zusammenarbeit: Geschäftsführung, andere Projektleiter, Stakeholder, externe Partner
            - Berufliche Stärken: Stratege, Führungsexpertise, Finanzexperte, Entscheidungsfähigkeit
            - Erfolgsmessung: Kostenreduktion, Prozessdurchlaufzeit, ROI, Projekterfolg
            - Ziele: Effizienzsteigerung, Kostensenkung, Transparenz, strategische Ausrichtung
            - Verantwortlich für technische Systeme oder Software: NEIN (nur Verantwortung, nicht Umsetzung)
            - Trifft hauptsächlich operative Entscheidungen: **NEIN** (strategische Entscheidungen)
            - Leitet Projekte oder Teams: **JA**

            **KLASSIFIKATIONS-ALGORITHMUS:**
            
            **Schritt 1: Analysiere die Ja/Nein-Antworten (höchstes Gewicht)**
            - "Treffen Sie hauptsächlich operative Entscheidungen?" = JA → +40% für "fach"
            - "Sind Sie verantwortlich für technische Systeme oder Software?" = JA → +40% für "it"
            - "Leiten Sie Projekte oder Teams?" = JA → +40% für "management"
            
            **Schritt 2: Analysiere die Rollenbezeichnung**
            Suche nach Schlüsselwörtern in der Antwort zur Rolle/Funktion:
            - IT-Begriffe (Admin, Entwickler, DevOps, Architekt, System) → +30% für "it"
            - Fach-Begriffe (Sachbearbeiter, Fachbereich, Prozess, Bearbeitung) → +30% für "fach"
            - Management-Begriffe (Leiter, Manager, Führung, Projekt, Chef) → +30% für "management"
            
            **Schritt 3: Analysiere Aufgaben und Verantwortung**
            - Technische Aufgaben (Server, API, Code, Deployment) → +15% für "it"
            - Operative Aufgaben (Bearbeitung, Prüfung, Tickets, Workflow) → +15% für "fach"
            - Strategische Aufgaben (Planung, Budget, Strategie, Steuerung) → +15% für "management"
            
            **Schritt 4: Analysiere Probleme/Herausforderungen**
            - Technische Probleme (Ausfall, Integration, Performance) → +10% für "it"
            - Operative Probleme (Fehler, Rückfragen, Arbeitslast) → +10% für "fach"
            - Strategische Probleme (Verzögerung, Transparenz, Budget) → +10% für "management"
            
            **Schritt 5: Analysiere Erfolgsmessung**
            - Technische Metriken (Verfügbarkeit, Performance, Automatisierung) → +5% für "it"
            - Operative Metriken (Bearbeitungszeit, Fehlerquote) → +5% für "fach"
            - Business-Metriken (Kosten, ROI, Durchlaufzeit) → +5% für "management"

            **WICHTIG:**
            - Starte mit Basis-Score von 0.0 für alle Rollen
            - Addiere die Prozentpunkte basierend auf den Antworten
            - Der finale Score sollte zwischen 0.0 und 1.0 liegen
            - Wenn mehrere Rollen ähnliche Scores haben (Differenz < 0.2), setze niedrigere Scores für Unsicherheit
            - Bei widersprüchlichen Antworten (z.B. "operative Entscheidungen"=Ja aber "Projektleitung"=Ja) → reduziere alle Scores um 0.1

            Antworte AUSSCHLIESSLICH im folgenden JSON-Format:
            {
            "candidates": [
                {"role": "it|fach|management", "score": 0.0-1.0},
                {"role": "...", "score": 0.0-1.0},
                {"role": "...", "score": 0.0-1.0}
            ],
            "explain": "Kurze Begründung (2-3 Sätze) mit konkreten Hinweisen aus den Antworten"
            }

            Sortiere die candidates nach Score absteigend. Gib IMMER alle 3 Rollen zurück, auch wenn manche sehr niedrige Scores haben.
            """
        }
        
        # Bereite die Antworten für das LLM auf
        answers_text = self._format_answers_for_llm(answers)
        
        print(f"\n🔍 DEBUG: Starte Rollenklassifikation mit {len(answers)} Antworten")
        print(f"📝 DEBUG: Formatierte Antworten:\n{answers_text}")
        
        user = {
            "role": "user",
            "content": f"""Bitte klassifiziere die Rolle dieser Person basierend auf folgenden Antworten:

{answers_text}

Welche Rolle hat diese Person am wahrscheinlichsten: IT, Fach oder Management?
Antworte im JSON-Format wie beschrieben."""
        }
        
        try:
            # LLM-Klassifikation mit JSON-Mode
            print("🤖 DEBUG: Sende Anfrage an Mistral LLM...")
            res = self.llm.complete(
                messages=[system, user],
                json_mode={"type": "json_object"},
            )
            
            payload = res.choices[0].message.content
            print(f"📥 DEBUG: LLM Antwort erhalten: {payload[:200]}...")
            
            # Parse JSON response
            result = self._parse_llm_response(payload)
            print(f"✅ DEBUG: JSON geparst: {result}")
            result["source"] = "llm"
            
            # Validiere und normalisiere die Rollen
            result = self._validate_and_normalize(result)
            print(f"🎯 DEBUG: Validiertes Ergebnis: {result}")
            
            if not result.get("candidates"):
                print("⚠️  DEBUG: Keine Kandidaten nach Validierung!")
            
            return result
            
        except Exception as e:
            print(f"❌ DEBUG: Exception bei LLM-Klassifikation: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: Returniere unsichere Klassifikation
            return {
                "candidates": [
                    {"role": "fach", "score": 0.4},
                    {"role": "it", "score": 0.3},
                    {"role": "management", "score": 0.3}
                ],
                "explain": "Automatische Klassifikation fehlgeschlagen, Standardrolle verwendet",
                "source": "fallback",
                "error": str(e)
            }
    
    def _format_answers_for_llm(self, answers: Dict[str, str]) -> str:
        """Formatiert die Antworten in lesbarer Form für das LLM"""
        formatted = []
        for question_id, answer in answers.items():
            # Entferne technische IDs und mache es lesbarer
            readable_id = question_id.replace("_", " ").title()
            formatted.append(f"- {readable_id}: {answer}")
        return "\n".join(formatted)
    
    def _parse_llm_response(self, payload: str) -> Dict[str, Any]:
        """Parst die LLM-Antwort und extrahiert JSON"""
        try:
            # Versuche direktes JSON-Parsing
            return json.loads(payload)
        except json.JSONDecodeError:
            # Fallback: Suche nach JSON-Block im Text
            m = re.search(r"\{.*\}", payload, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise ValueError(f"Konnte kein gültiges JSON in der Antwort finden: {payload}")
    
    def _validate_and_normalize(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validiert und normalisiert das Klassifikationsergebnis"""
        valid_roles = {"it", "fach", "management"}
        
        # Stelle sicher, dass candidates existiert
        if "candidates" not in result or not isinstance(result["candidates"], list):
            result["candidates"] = []
        
        # Filtere und validiere Kandidaten
        validated_candidates = []
        for candidate in result["candidates"]:
            if isinstance(candidate, dict) and "role" in candidate and "score" in candidate:
                role = candidate["role"].lower()
                if role in valid_roles:
                    # Normalisiere Score auf 0-1 Range
                    score = float(candidate["score"])
                    score = max(0.0, min(1.0, score))
                    validated_candidates.append({
                        "role": role,
                        "score": round(score, 2)
                    })
        
        # Sortiere nach Score absteigend
        validated_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        result["candidates"] = validated_candidates
        return result
