"""
PDF-Generator für Prozessdokumentation
Erstellt professionelle PDF-Dokumente aus Interview-Daten aller Rollen
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

from app.llm.mistral_client import MistralClient


class PDFDocumentGenerator:
    """
    Generiert professionelle PDF-Prozessdokumentationen aus Interview-Daten.
    Nutzt LLM zur intelligenten Aufbereitung der Inhalte.
    """
    
    def __init__(self, llm_client: Optional[MistralClient] = None):
        self.llm = llm_client
        self.styles = self._create_styles()
    
    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Erstellt die PDF-Stile"""
        base_styles = getSampleStyleSheet()
        
        styles = {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=base_styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor('#2c3e50'),
                alignment=TA_CENTER
            ),
            'subtitle': ParagraphStyle(
                'CustomSubtitle',
                parent=base_styles['Normal'],
                fontSize=12,
                spaceAfter=20,
                textColor=colors.HexColor('#7f8c8d'),
                alignment=TA_CENTER
            ),
            'section_header': ParagraphStyle(
                'SectionHeader',
                parent=base_styles['Heading2'],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=12,
                textColor=colors.HexColor('#2980b9'),
                borderPadding=(0, 0, 5, 0)
            ),
            'subsection_header': ParagraphStyle(
                'SubsectionHeader',
                parent=base_styles['Heading3'],
                fontSize=13,
                spaceBefore=15,
                spaceAfter=8,
                textColor=colors.HexColor('#34495e')
            ),
            'body': ParagraphStyle(
                'CustomBody',
                parent=base_styles['Normal'],
                fontSize=10,
                spaceAfter=8,
                alignment=TA_JUSTIFY,
                leading=14
            ),
            'body_bold': ParagraphStyle(
                'CustomBodyBold',
                parent=base_styles['Normal'],
                fontSize=10,
                spaceAfter=4,
                fontName='Helvetica-Bold'
            ),
            'bullet': ParagraphStyle(
                'CustomBullet',
                parent=base_styles['Normal'],
                fontSize=10,
                leftIndent=20,
                spaceAfter=4
            ),
            'role_header': ParagraphStyle(
                'RoleHeader',
                parent=base_styles['Heading3'],
                fontSize=14,
                spaceBefore=15,
                spaceAfter=10,
                textColor=colors.HexColor('#27ae60'),
                backColor=colors.HexColor('#ecf0f1'),
                borderPadding=10
            ),
            'footer': ParagraphStyle(
                'Footer',
                parent=base_styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#95a5a6'),
                alignment=TA_CENTER
            )
        }
        
        return styles
    
    def generate_pdf(
        self, 
        session_data: Dict[str, Any],
        completed_interviews: List[Dict[str, Any]] = None
    ) -> bytes:
        """
        Generiert ein vollständiges PDF aus den Interview-Daten.
        
        Args:
            session_data: Aktuelle Session-Daten
            completed_interviews: Liste abgeschlossener Rollen-Interviews
            
        Returns:
            PDF als Bytes
        """
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Sammle alle Interview-Daten
        all_interviews = self._collect_all_interviews(session_data, completed_interviews)
        
        # Generiere aufbereitete Inhalte mit LLM
        processed_content = self._process_with_llm(all_interviews)
        
        # Baue PDF-Elemente
        elements = []
        
        # Titelseite
        elements.extend(self._create_title_page(all_interviews))
        
        # Abschnitt 1: Beteiligte & allgemeine Informationen
        elements.extend(self._create_section_general(processed_content, all_interviews))
        
        # Abschnitt 2: Rollenspezifische Informationen
        elements.extend(self._create_section_roles(processed_content, all_interviews))
        
        # Abschnitt 3: Prozessablauf
        elements.extend(self._create_section_process(processed_content))
        
        # Abschnitt 4: Potenziale & Chancen
        elements.extend(self._create_section_potentials(processed_content))
        
        # Abschnitt 5: Ergänzende Infos
        elements.extend(self._create_section_additional(processed_content))
        
        # Anhang: Vollständige Antworten
        elements.extend(self._create_appendix(all_interviews))
        
        # PDF generieren
        doc.build(elements)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def _collect_all_interviews(
        self, 
        session_data: Dict[str, Any],
        completed_interviews: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Sammelt alle Interview-Daten aus Session und abgeschlossenen Interviews"""
        interviews = []
        
        # Mapping für Rollen-Labels
        role_labels = {
            'fach': 'Fachabteilung / Mitarbeitende',
            'it': 'IT-Verantwortliche',
            'management': 'Management'
        }
        
        # Abgeschlossene Interviews
        if completed_interviews:
            for interview in completed_interviews:
                role = interview.get('role', 'unbekannt')
                role_label = interview.get('role_label') or role_labels.get(role, role.capitalize())
                interviews.append({
                    'role': role,
                    'role_label': role_label,
                    'intake_questions': interview.get('intake_questions', []),
                    'role_questions': interview.get('role_questions', []),
                    'answers': interview.get('answers', {}),
                    'schema_fields': interview.get('schema_fields', {}),
                    'completed_at': interview.get('completed_at', '')
                })
        
        # Aktuelles Interview (falls Fortschritt vorhanden)
        if session_data.get('answers') and len(session_data.get('answers', {})) > 0:
            # Prüfe ob nicht schon in completed_interviews
            current_role = session_data.get('role', '')
            
            # Nur hinzufügen wenn eine Rolle erkannt wurde und nicht bereits enthalten
            if current_role:
                already_included = any(
                    i.get('role') == current_role 
                    for i in interviews
                )
                
                if not already_included:
                    # Bestimme korrektes Label
                    current_label = session_data.get('role_label') or role_labels.get(current_role, current_role.capitalize())
                    
                    interviews.append({
                        'role': current_role,
                        'role_label': current_label,
                        'intake_questions': session_data.get('intake_questions', []),
                        'role_questions': session_data.get('role_questions', []),
                        'answers': session_data.get('answers', {}),
                        'schema_fields': session_data.get('schema_fields', {}),
                        'completed_at': datetime.now().isoformat()
                    })
        
        return interviews
    
    def _process_with_llm(self, interviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verarbeitet Interview-Daten mit LLM für strukturierte Ausgabe"""
        
        if not self.llm or not interviews:
            return self._fallback_processing(interviews)
        
        # Bereite alle Q&A-Paare auf
        all_qa_text = self._format_interviews_for_llm(interviews)
        
        system_prompt = """Du bist ein Experte für Prozessdokumentation und Business-Analyse.

Deine Aufgabe: Analysiere die Interview-Antworten mehrerer Stakeholder und erstelle eine strukturierte Zusammenfassung.

**WICHTIGE REGELN:**
1. Extrahiere NUR Informationen aus den tatsächlichen Antworten
2. Erfinde KEINE Details hinzu
3. Konsolidiere Informationen aus verschiedenen Rollen
4. Identifiziere Überschneidungen und unterschiedliche Perspektiven
5. Formuliere professionell und präzise
6. Bei fehlenden Informationen: "Nicht im Interview erfasst"

**AUSGABEFORMAT (JSON):**
{
  "prozessname": "Name des Prozesses",
  "kurzbeschreibung": "2-3 Sätze Zusammenfassung",
  "beteiligte_rollen": ["Rolle1", "Rolle2"],
  "genutzte_systeme": ["System1", "System2"],
  "prozessziele": ["Ziel1", "Ziel2"],
  "hauptprobleme": ["Problem1", "Problem2"],
  "prozessschritte": ["Schritt1", "Schritt2", "Schritt3"],
  "eingaben": ["Eingabe1", "Eingabe2"],
  "ausgaben": ["Ausgabe1", "Ausgabe2"],
  "entscheidungspunkte": ["Entscheidung1", "Entscheidung2"],
  "varianten_sonderfaelle": ["Variante1", "Sonderfall1"],
  "automatisierungspotenziale": ["Potenzial1", "Potenzial2"],
  "fehlerquellen": ["Fehler1", "Fehler2"],
  "verbesserungsideen": ["Idee1", "Idee2"],
  "zusatzinfos": "Weitere relevante Informationen",
  "offene_fragen": ["Frage1", "Frage2"]
}

Antworte NUR mit dem JSON-Objekt, keine Erklärungen."""

        user_prompt = f"""Analysiere diese Interview-Daten aus einer Prozessaufnahme und erstelle die strukturierte Zusammenfassung:

{all_qa_text}

Erstelle das JSON-Objekt mit allen extrahierten Informationen."""

        try:
            response = self.llm.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            content = response.choices[0].message.content
            
            # Extrahiere JSON aus Antwort
            import json
            
            # Versuche JSON zu parsen (mit Cleanup)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            
            return self._fallback_processing(interviews)
            
        except Exception as e:
            print(f"⚠️  LLM-Verarbeitung fehlgeschlagen: {e}")
            return self._fallback_processing(interviews)
    
    def _format_interviews_for_llm(self, interviews: List[Dict[str, Any]]) -> str:
        """Formatiert alle Interviews für LLM-Verarbeitung"""
        parts = []
        
        for interview in interviews:
            role = interview.get('role_label', 'Unbekannt')
            parts.append(f"\n{'='*50}")
            parts.append(f"INTERVIEW: {role}")
            parts.append(f"{'='*50}\n")
            
            answers = interview.get('answers', {})
            schema_fields = interview.get('schema_fields', {})
            
            # Intake-Fragen
            for q in interview.get('intake_questions', []):
                q_id = q.get('id', '')
                q_text = q.get('text', '')
                answer = answers.get(q_id, '')
                if answer:
                    parts.append(f"Frage: {q_text}")
                    parts.append(f"Antwort: {answer}\n")
            
            # Rollenspezifische Fragen
            for q in interview.get('role_questions', []):
                field_id = q.get('field_id', '')
                q_text = q.get('text', '')
                theme = q.get('theme_name', '')
                
                # Hole Antwort aus schema_fields
                if field_id in schema_fields:
                    field_data = schema_fields[field_id]
                    if isinstance(field_data, dict):
                        answer = field_data.get('raw_answer', field_data.get('value', ''))
                    else:
                        answer = str(field_data)
                    
                    if answer:
                        if theme:
                            parts.append(f"[{theme}]")
                        parts.append(f"Frage: {q_text}")
                        parts.append(f"Antwort: {answer}\n")
        
        return "\n".join(parts)
    
    def _fallback_processing(self, interviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback wenn LLM nicht verfügbar"""
        roles = []
        systems = []
        problems = []
        
        for interview in interviews:
            role = interview.get('role_label', '')
            if role:
                roles.append(role)
            
            # Extrahiere einfache Informationen
            for answer in interview.get('answers', {}).values():
                if isinstance(answer, str) and len(answer) > 0:
                    # Einfache Keyword-Extraktion
                    if any(kw in answer.lower() for kw in ['system', 'software', 'tool', 'excel', 'sap']):
                        systems.append(answer[:100])
                    if any(kw in answer.lower() for kw in ['problem', 'schwierig', 'fehler', 'manuell']):
                        problems.append(answer[:100])
        
        return {
            "prozessname": "Prozessdokumentation",
            "kurzbeschreibung": "Dokumentation basierend auf Stakeholder-Interviews",
            "beteiligte_rollen": roles,
            "genutzte_systeme": systems[:5],
            "prozessziele": ["Aus Interviews extrahiert"],
            "hauptprobleme": problems[:5],
            "prozessschritte": [],
            "eingaben": [],
            "ausgaben": [],
            "entscheidungspunkte": [],
            "varianten_sonderfaelle": [],
            "automatisierungspotenziale": [],
            "fehlerquellen": [],
            "verbesserungsideen": [],
            "zusatzinfos": "",
            "offene_fragen": []
        }
    
    def _create_title_page(self, interviews: List[Dict[str, Any]]) -> List:
        """Erstellt die Titelseite"""
        elements = []
        
        elements.append(Spacer(1, 3*cm))
        
        elements.append(Paragraph(
            "PROZESSDOKUMENTATION",
            self.styles['title']
        ))
        
        elements.append(Paragraph(
            "KI-gestützte Befragungsanalyse",
            self.styles['subtitle']
        ))
        
        elements.append(Spacer(1, 1*cm))
        
        # Datum
        date_str = datetime.now().strftime("%d.%m.%Y")
        elements.append(Paragraph(
            f"Erstellt am: {date_str}",
            self.styles['subtitle']
        ))
        
        # Anzahl Interviews
        num_interviews = len(interviews)
        roles = [i.get('role_label', 'Unbekannt') for i in interviews]
        
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(
            f"Basierend auf {num_interviews} Interview(s)",
            self.styles['subtitle']
        ))
        
        if roles:
            elements.append(Paragraph(
                f"Befragte Rollen: {', '.join(roles)}",
                self.styles['subtitle']
            ))
        
        elements.append(PageBreak())
        
        return elements
    
    def _create_section_general(
        self, 
        content: Dict[str, Any],
        interviews: List[Dict[str, Any]]
    ) -> List:
        """Abschnitt 1: Beteiligte & allgemeine Informationen"""
        elements = []
        
        elements.append(Paragraph(
            "1. Beteiligte & Allgemeine Informationen zum Prozess",
            self.styles['section_header']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Prozessname
        elements.append(Paragraph("Prozessname", self.styles['body_bold']))
        elements.append(Paragraph(
            content.get('prozessname', 'Nicht spezifiziert'),
            self.styles['body']
        ))
        
        # Kurzbeschreibung
        elements.append(Paragraph("Kurzbeschreibung des Prozesses", self.styles['body_bold']))
        elements.append(Paragraph(
            content.get('kurzbeschreibung', 'Nicht spezifiziert'),
            self.styles['body']
        ))
        
        # Beteiligte Rollen
        elements.append(Paragraph("Beteiligte Rollen", self.styles['body_bold']))
        roles = content.get('beteiligte_rollen', [])
        if roles:
            elements.append(self._create_bullet_list(roles))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        # Genutzte Systeme
        elements.append(Paragraph("Genutzte Systeme oder Tools", self.styles['body_bold']))
        systems = content.get('genutzte_systeme', [])
        if systems:
            elements.append(self._create_bullet_list(systems))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        # Prozessziele
        elements.append(Paragraph("Prozessziele", self.styles['body_bold']))
        goals = content.get('prozessziele', [])
        if goals:
            elements.append(self._create_bullet_list(goals))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        # Hauptprobleme
        elements.append(Paragraph("Häufigste Probleme oder Herausforderungen", self.styles['body_bold']))
        problems = content.get('hauptprobleme', [])
        if problems:
            elements.append(self._create_bullet_list(problems))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_section_roles(
        self, 
        content: Dict[str, Any],
        interviews: List[Dict[str, Any]]
    ) -> List:
        """Abschnitt 2: Rollenspezifische Informationen"""
        elements = []
        
        elements.append(Paragraph(
            "2. Rollenspezifische Informationen",
            self.styles['section_header']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        for interview in interviews:
            role_label = interview.get('role_label', 'Unbekannt')
            role = interview.get('role', 'unbekannt')
            
            # Rollen-Header
            elements.append(Paragraph(
                f"📋 {role_label}",
                self.styles['role_header']
            ))
            
            # Extrahiere rollenspezifische Infos
            answers = interview.get('answers', {})
            schema_fields = interview.get('schema_fields', {})
            
            # Rollenaufgabe
            elements.append(Paragraph("Rollenaufgabe im Prozess", self.styles['body_bold']))
            role_tasks = self._extract_role_info(interview, ['aufgaben', 'tätigkeiten', 'hauptaufgaben'])
            elements.append(Paragraph(role_tasks or "Nicht spezifiziert", self.styles['body']))
            
            # Schmerzpunkte
            elements.append(Paragraph("Schmerzpunkte der Rolle", self.styles['body_bold']))
            pain_points = self._extract_role_info(interview, ['problem', 'schwierig', 'herausforderung', 'workaround'])
            elements.append(Paragraph(pain_points or "Nicht spezifiziert", self.styles['body']))
            
            # Kernantworten als Zusammenfassung
            elements.append(Paragraph("Rollenspezifische Kernantworten", self.styles['body_bold']))
            
            # Zeige wichtigste Antworten
            key_answers = self._get_key_answers(interview, max_answers=5)
            if key_answers:
                for q_text, answer in key_answers:
                    elements.append(Paragraph(f"<b>{q_text}</b>", self.styles['bullet']))
                    elements.append(Paragraph(f"{answer}", self.styles['body']))
            else:
                elements.append(Paragraph("Keine Kernantworten verfügbar", self.styles['body']))
            
            elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_section_process(self, content: Dict[str, Any]) -> List:
        """Abschnitt 3: Überblick über den Prozessablauf"""
        elements = []
        
        elements.append(Paragraph(
            "3. Überblick über den Prozessablauf",
            self.styles['section_header']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Prozessschritte
        elements.append(Paragraph("Schritte des Hauptprozesses", self.styles['body_bold']))
        steps = content.get('prozessschritte', [])
        if steps:
            elements.append(self._create_numbered_list(steps))
        else:
            elements.append(Paragraph("Nicht im Interview erfasst", self.styles['body']))
        
        # Eingaben
        elements.append(Paragraph("Eingaben im Prozess", self.styles['body_bold']))
        inputs = content.get('eingaben', [])
        if inputs:
            elements.append(self._create_bullet_list(inputs))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        # Ausgaben
        elements.append(Paragraph("Ausgaben im Prozess", self.styles['body_bold']))
        outputs = content.get('ausgaben', [])
        if outputs:
            elements.append(self._create_bullet_list(outputs))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        # Entscheidungspunkte
        elements.append(Paragraph("Wichtige Entscheidungspunkte", self.styles['body_bold']))
        decisions = content.get('entscheidungspunkte', [])
        if decisions:
            elements.append(self._create_bullet_list(decisions))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        # Varianten
        elements.append(Paragraph("Varianten oder Sonderfälle", self.styles['body_bold']))
        variants = content.get('varianten_sonderfaelle', [])
        if variants:
            elements.append(self._create_bullet_list(variants))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_section_potentials(self, content: Dict[str, Any]) -> List:
        """Abschnitt 4: Potenziale & Chancen"""
        elements = []
        
        elements.append(Paragraph(
            "4. Potenziale & Chancen",
            self.styles['section_header']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Automatisierungspotenziale
        elements.append(Paragraph("Automatisierungspotenziale", self.styles['body_bold']))
        automation = content.get('automatisierungspotenziale', [])
        if automation:
            elements.append(self._create_bullet_list(automation))
        else:
            elements.append(Paragraph("Nicht im Interview identifiziert", self.styles['body']))
        
        # Fehlerquellen
        elements.append(Paragraph("Häufige Fehlerquellen", self.styles['body_bold']))
        errors = content.get('fehlerquellen', [])
        if errors:
            elements.append(self._create_bullet_list(errors))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        
        # Verbesserungsideen
        elements.append(Paragraph("Verbesserungsideen der Stakeholder", self.styles['body_bold']))
        ideas = content.get('verbesserungsideen', [])
        if ideas:
            elements.append(self._create_bullet_list(ideas))
        else:
            elements.append(Paragraph("Nicht im Interview genannt", self.styles['body']))
        
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_section_additional(self, content: Dict[str, Any]) -> List:
        """Abschnitt 5: Ergänzende Infos"""
        elements = []
        
        elements.append(Paragraph(
            "5. Ergänzende Informationen",
            self.styles['section_header']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Zusatzinformationen
        elements.append(Paragraph("Zusatzinformationen", self.styles['body_bold']))
        additional = content.get('zusatzinfos', '')
        elements.append(Paragraph(
            additional if additional else "Keine weiteren Informationen",
            self.styles['body']
        ))
        
        # Offene Fragen
        elements.append(Paragraph("Offene Fragen", self.styles['body_bold']))
        questions = content.get('offene_fragen', [])
        if questions:
            elements.append(self._create_bullet_list(questions))
        else:
            elements.append(Paragraph("Keine offenen Fragen dokumentiert", self.styles['body']))
        
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_appendix(self, interviews: List[Dict[str, Any]]) -> List:
        """Anhang: Vollständige Interview-Antworten"""
        elements = []
        
        elements.append(PageBreak())
        
        elements.append(Paragraph(
            "Anhang: Vollständige Interview-Antworten",
            self.styles['section_header']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        for interview in interviews:
            role_label = interview.get('role_label', 'Unbekannt')
            
            elements.append(Paragraph(
                f"Interview: {role_label}",
                self.styles['subsection_header']
            ))
            
            answers = interview.get('answers', {})
            schema_fields = interview.get('schema_fields', {})
            
            # Intake-Fragen
            for q in interview.get('intake_questions', []):
                q_id = q.get('id', '')
                q_text = q.get('text', '')
                answer = answers.get(q_id, '')
                
                if answer:
                    elements.append(Paragraph(f"<b>F:</b> {q_text}", self.styles['body']))
                    elements.append(Paragraph(f"<b>A:</b> {answer}", self.styles['body']))
                    elements.append(Spacer(1, 0.2*cm))
            
            # Rollenspezifische Fragen
            for q in interview.get('role_questions', []):
                field_id = q.get('field_id', '')
                q_text = q.get('text', '')
                
                if field_id in schema_fields:
                    field_data = schema_fields[field_id]
                    if isinstance(field_data, dict):
                        answer = field_data.get('raw_answer', field_data.get('value', ''))
                    else:
                        answer = str(field_data)
                    
                    if answer:
                        elements.append(Paragraph(f"<b>F:</b> {q_text}", self.styles['body']))
                        elements.append(Paragraph(f"<b>A:</b> {answer}", self.styles['body']))
                        elements.append(Spacer(1, 0.2*cm))
            
            elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_bullet_list(self, items: List[str]) -> ListFlowable:
        """Erstellt eine Aufzählungsliste"""
        list_items = []
        for item in items:
            if item:
                list_items.append(ListItem(
                    Paragraph(str(item), self.styles['body']),
                    bulletColor=colors.HexColor('#3498db')
                ))
        
        return ListFlowable(
            list_items,
            bulletType='bullet',
            start='•',
            leftIndent=20
        )
    
    def _create_numbered_list(self, items: List[str]) -> ListFlowable:
        """Erstellt eine nummerierte Liste"""
        list_items = []
        for item in items:
            if item:
                list_items.append(ListItem(
                    Paragraph(str(item), self.styles['body'])
                ))
        
        return ListFlowable(
            list_items,
            bulletType='1',
            leftIndent=20
        )
    
    def _extract_role_info(
        self, 
        interview: Dict[str, Any], 
        keywords: List[str]
    ) -> str:
        """Extrahiert rollenspezifische Informationen basierend auf Keywords"""
        answers = interview.get('answers', {})
        schema_fields = interview.get('schema_fields', {})
        
        # Durchsuche Antworten
        relevant_answers = []
        
        for q in interview.get('intake_questions', []) + interview.get('role_questions', []):
            q_text = q.get('text', '').lower()
            q_id = q.get('id', q.get('field_id', ''))
            
            # Prüfe ob Frage zu Keywords passt
            if any(kw in q_text for kw in keywords):
                answer = answers.get(q_id, '')
                if not answer and q_id in schema_fields:
                    field_data = schema_fields[q_id]
                    if isinstance(field_data, dict):
                        answer = field_data.get('raw_answer', '')
                    else:
                        answer = str(field_data)
                
                if answer:
                    relevant_answers.append(answer)
        
        return " | ".join(relevant_answers[:3]) if relevant_answers else ""
    
    def _get_key_answers(
        self, 
        interview: Dict[str, Any], 
        max_answers: int = 5
    ) -> List[tuple]:
        """Holt die wichtigsten Frage-Antwort-Paare"""
        key_answers = []
        
        answers = interview.get('answers', {})
        schema_fields = interview.get('schema_fields', {})
        
        # Priorität: Rollenspezifische Fragen
        for q in interview.get('role_questions', []):
            if len(key_answers) >= max_answers:
                break
                
            field_id = q.get('field_id', '')
            q_text = q.get('text', '')
            
            if field_id in schema_fields:
                field_data = schema_fields[field_id]
                if isinstance(field_data, dict):
                    answer = field_data.get('raw_answer', field_data.get('value', ''))
                else:
                    answer = str(field_data)
                
                if answer and len(answer) > 10:
                    key_answers.append((q_text, answer[:300] + "..." if len(answer) > 300 else answer))
        
        # Falls nicht genug: Intake-Fragen
        for q in interview.get('intake_questions', []):
            if len(key_answers) >= max_answers:
                break
                
            q_id = q.get('id', '')
            q_text = q.get('text', '')
            answer = answers.get(q_id, '')
            
            if answer and len(answer) > 10:
                key_answers.append((q_text, answer[:300] + "..." if len(answer) > 300 else answer))
        
        return key_answers
