from typing import Dict, List, Any
from app.llm.mistral_client import MistralClient

class DocGenerator:
    def __init__(self, llm: MistralClient):
        self.llm = llm

    def render_it(self, questions: List[Dict[str, Any]], answers: Dict[str, str]) -> str:
        """
        Generiert eine strukturierte IT-Prozessdokumentation aus den Interview-Antworten.
        
        Args:
            questions: Liste aller gestellten Fragen mit Text und ID
            answers: Dictionary mit question_id -> answer
            
        Returns:
            Formatierte Prozessdokumentation
        """
        # Bereite Interview-Transkript auf
        qa_pairs = []
        for q in questions:
            q_id = q.get("id", "")
            q_text = q.get("text", "")
            answer = answers.get(q_id, "Keine Antwort")
            qa_pairs.append(f"**Frage:** {q_text}\n**Antwort:** {answer}\n")
        
        interview_transcript = "\n".join(qa_pairs)
        
        system_prompt = {
            "role": "system",
            "content": """Du bist ein Experte für technische Prozessdokumentation. 

Deine Aufgabe: Erstelle aus einem Interview-Transkript eine strukturierte, professionelle IT-Prozessdokumentation.

**WICHTIGE REGELN:**
1. Extrahiere nur Informationen, die tatsächlich im Interview genannt wurden
2. Erfinde KEINE Details hinzu
3. Wenn Informationen fehlen, schreibe "Nicht spezifiziert" oder lasse den Punkt aus
4. Formuliere präzise und technisch korrekt
5. Nutze Bulletpoints für bessere Lesbarkeit
6. Halte es kompakt (max. 2-3 Sätze pro Abschnitt)

**STRUKTUR:**
Die Dokumentation muss folgende Abschnitte enthalten:

1. **Prozessziel**
   - Was soll erreicht werden?
   - Welches Problem wird gelöst?

2. **Trigger / Auslöser**
   - Was startet den Prozess?
   - Welche Events oder Bedingungen?

3. **Eingangsdaten**
   - Welche Daten werden benötigt?
   - Von wo kommen sie?

4. **Beteiligte Systeme**
   - Welche technischen Systeme sind involviert?
   - Hardware, Software, Services?

5. **Ausgabedaten / Empfänger**
   - Was wird produziert?
   - Wer nutzt die Ergebnisse?

6. **IT-Architektur**
   - Wie ist die technische Infrastruktur aufgebaut?
   - Schnittstellen, APIs, Protokolle?

7. **Authentifizierung & Sicherheit**
   - Welche Sicherheitsmaßnahmen gibt es?
   - Zugriffskontrolle, Verschlüsselung?

8. **Betrieb & Monitoring**
   - Wie wird der Prozess betrieben?
   - Überwachung, Fehlerbehandlung?

Antworte NUR mit der fertigen Dokumentation, keine Meta-Kommentare."""
        }
        
        user_prompt = {
            "role": "user",
            "content": f"""Erstelle eine strukturierte IT-Prozessdokumentation aus diesem Interview:

{interview_transcript}

Extrahiere die relevanten Informationen und ordne sie den passenden Abschnitten zu.
Verwende Markdown-Formatierung für bessere Lesbarkeit."""
        }
        
        try:
            response = self.llm.complete(
                messages=[system_prompt, user_prompt],
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"⚠️  Fehler bei Dokumentengenerierung: {e}")
            return self._generate_fallback_doc(questions, answers)
    
    def _generate_fallback_doc(self, questions: List[Dict[str, Any]], answers: Dict[str, str]) -> str:
        """Einfache Fallback-Dokumentation wenn LLM fehlschlägt."""
        doc = "# PROZESSDOKUMENTATION\n\n"
        doc += "## Interview-Antworten\n\n"
        
        for q in questions:
            q_id = q.get("id", "")
            q_text = q.get("text", "")
            answer = answers.get(q_id, "Keine Antwort")
            doc += f"**{q_text}**\n{answer}\n\n"
        
        return doc
