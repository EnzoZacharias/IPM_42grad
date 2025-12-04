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
        """
        Verarbeitet Interview-Daten mit LLM für professionelle, analysierte Ausgabe.
        Die Antworten werden nicht nur extrahiert, sondern analysiert, interpretiert 
        und als professionelle allgemeine Aussagen aufbereitet.
        """
        
        # Debug-Ausgabe
        print(f"🔍 LLM-Client vorhanden: {self.llm is not None}")
        print(f"🔍 Interviews vorhanden: {len(interviews) if interviews else 0}")

        if not self.llm:
            print("⚠️  Kein LLM-Client verfügbar - nutze Fallback-Verarbeitung")
            return self._fallback_processing(interviews)
            
        if not interviews:
            print("⚠️  Keine Interviews vorhanden - nutze Fallback-Verarbeitung")
            return self._fallback_processing(interviews)

        # Bereite alle Q&A-Paare auf
        all_qa_text = self._format_interviews_for_llm(interviews)
        
        print(f"📝 LLM-Analyse gestartet mit {len(all_qa_text)} Zeichen Text")

        system_prompt = """Du bist ein erfahrener Business-Analyst und Prozessberater, der Interview-Ergebnisse in professionelle Prozessdokumentationen umwandelt.

**DEINE AUFGABE:**
Analysiere die Interview-Antworten TIEFGREIFEND und erstelle daraus eine PROFESSIONELLE Prozessdokumentation.
Du sollst die Antworten NICHT einfach kopieren oder zusammenfassen, sondern:
1. Die Kernaussagen ANALYSIEREN und INTERPRETIEREN
2. Daraus allgemeingültige, professionelle STATEMENTS formulieren
3. Implikationen und Zusammenhänge ERKENNEN und darstellen
4. Konkrete, umsetzbare ERKENNTNISSE ableiten

**STIL DER AUSSAGEN:**
- Professionell und sachlich formuliert
- Als allgemeine Feststellungen (nicht "der Befragte sagte...")
- Konkret und spezifisch (keine vagen Aussagen)
- Mit Kontext und Begründung wo sinnvoll
- Immer mindestens 2-3 vollständige Sätze pro Punkt

**BEISPIEL für gute Aussagen:**
SCHLECHT: "Es gibt Probleme mit manuellen Prozessen"
GUT: "Die Dateneingabe erfolgt derzeit überwiegend manuell über Excel-Listen, was zu erhöhtem Zeitaufwand und einer Fehlerquote von geschätzt 5-10% führt. Dies betrifft insbesondere die tägliche Erfassung von Produktionsdaten und erfordert regelmäßige Nacharbeit durch das Team."

**AUSGABEFORMAT (JSON):**
{
  "prozessname": "Präziser, beschreibender Name des Prozesses/Bereichs",
  
  "executive_summary": "Eine umfassende Management-Zusammenfassung (8-12 Sätze): Was wurde untersucht? Welche Haupterkenntnisse gibt es? Was sind die kritischsten Punkte? Welche Handlungsempfehlungen ergeben sich?",
  
  "ist_situation": "Detaillierte Beschreibung der aktuellen Situation (6-10 Sätze): Wie läuft der Prozess heute ab? Welche Ressourcen werden eingesetzt? Wie ist die Organisation aufgestellt?",
  
  "beteiligte_rollen": [
    "Rolle 1: Ausführliche Beschreibung der Verantwortlichkeiten, typischen Aufgaben und Position im Prozess (2-3 Sätze)",
    "Rolle 2: ..."
  ],
  
  "genutzte_systeme": [
    "System/Tool 1: Beschreibung des Einsatzzwecks, der Stärken und etwaiger Limitationen (2-3 Sätze)",
    "System/Tool 2: ..."
  ],
  
  "prozessziele": [
    "Ziel 1: Konkrete Beschreibung mit Kontext warum dieses Ziel wichtig ist (2-3 Sätze)",
    "Ziel 2: ..."
  ],
  
  "hauptprobleme": [
    "Problem 1: Detaillierte Analyse des Problems, seiner Ursachen und Auswirkungen (3-4 Sätze)",
    "Problem 2: ..."
  ],
  
  "prozessablauf_beschreibung": "Ausführliche narrative Beschreibung des Prozessablaufs (10-15 Sätze): Vom Auslöser bis zum Ergebnis, mit allen wichtigen Schritten, Entscheidungspunkten und Übergaben.",
  
  "prozessschritte": [
    "Schritt 1: Beschreibung der Aktivität, wer sie durchführt und was das Ergebnis ist",
    "Schritt 2: ..."
  ],
  
  "eingaben": [
    "Eingabe 1: Beschreibung der Daten/Dokumente/Informationen die in den Prozess fließen",
    "..."
  ],
  
  "ausgaben": [
    "Ausgabe 1: Beschreibung der Ergebnisse, Produkte oder Dokumente die entstehen",
    "..."
  ],
  
  "entscheidungspunkte": [
    "Entscheidung 1: Welche Entscheidung wird getroffen, nach welchen Kriterien, und welche Konsequenzen hat sie (2-3 Sätze)",
    "..."
  ],
  
  "varianten_sonderfaelle": [
    "Variante 1: Beschreibung wann dieser Sonderfall eintritt und wie damit umgegangen wird (2-3 Sätze)",
    "..."
  ],
  
  "automatisierungspotenziale": [
    "Potenzial 1: Konkrete Beschreibung was automatisiert werden könnte, welcher Aufwand geschätzt wird und welcher Nutzen zu erwarten ist (3-4 Sätze)",
    "..."
  ],
  
  "fehlerquellen_risiken": [
    "Risiko 1: Beschreibung der Fehlerquelle, wie häufig sie auftritt und welche Auswirkungen sie hat (2-3 Sätze)",
    "..."
  ],
  
  "verbesserungsempfehlungen": [
    "Empfehlung 1: Konkrete Handlungsempfehlung mit Begründung und erwartetem Nutzen (3-4 Sätze)",
    "..."
  ],
  
  "quick_wins": [
    "Quick Win 1: Schnell umsetzbare Verbesserung mit geringem Aufwand (2-3 Sätze)",
    "..."
  ],
  
  "strategische_massnahmen": [
    "Maßnahme 1: Längerfristige strategische Verbesserung (2-3 Sätze)",
    "..."
  ],
  
  "kennzahlen_metriken": [
    "KPI 1: Beschreibung der Kennzahl, aktueller Stand wenn bekannt, und Zielwert falls genannt",
    "..."
  ],
  
  "compliance_anforderungen": [
    "Anforderung 1: Regulatorische oder Compliance-Anforderung mit Relevanz für den Prozess",
    "..."
  ],
  
  "schnittstellen_abhaengigkeiten": [
    "Schnittstelle 1: Beschreibung der Verbindung zu anderen Bereichen/Systemen/Prozessen (2-3 Sätze)",
    "..."
  ],
  
  "offene_punkte": [
    "Offener Punkt 1: Was wurde nicht vollständig geklärt und sollte noch untersucht werden",
    "..."
  ],
  
  "fazit": "Abschließende Bewertung und Gesamteinschätzung (5-8 Sätze): Was sind die wichtigsten Erkenntnisse? Wie ist der Reifegrad des Prozesses? Was sollte priorisiert werden?"
}

**WICHTIG:** 
- Formuliere ALLE Punkte als professionelle, analytische Aussagen
- Jeder Listenpunkt sollte mindestens 2 vollständige Sätze enthalten
- Leite Erkenntnisse AB, kopiere nicht nur Antworten
- Antworte NUR mit dem JSON-Objekt, keine Einleitung oder Erklärung"""

        user_prompt = f"""Analysiere diese Interview-Daten aus einer Prozessaufnahme und erstelle eine UMFASSENDE, PROFESSIONELLE Prozessdokumentation.

WICHTIG: Analysiere und interpretiere die Antworten tiefgreifend. Formuliere alle Erkenntnisse als professionelle, allgemeingültige Aussagen - nicht als Zitate oder Zusammenfassungen der Befragten.

=== INTERVIEW-DATEN ===
{all_qa_text}
=== ENDE INTERVIEW-DATEN ===

Erstelle jetzt das vollständige JSON-Objekt mit allen analysierten Informationen. Sei detailliert, professionell und konkret in deinen Aussagen."""

        try:
            print("🤖 Sende Anfrage an LLM für tiefgreifende Analyse...")
            response = self.llm.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],)

            content = response.choices[0].message.content
            print(f"✅ LLM-Antwort erhalten: {len(content)} Zeichen")
            
            # Debug: Zeige Anfang der Antwort
            print(f"📄 LLM-Antwort (erste 500 Zeichen):\n{content[:500]}")

            # Extrahiere JSON aus Antwort
            import json

            # Versuche JSON zu parsen (mit Cleanup)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group()
                print(f"📄 Gefundenes JSON (erste 300 Zeichen): {json_str[:300]}")
                parsed = json.loads(json_str)
                
                # Fix: Falls LLM verschachtelte Struktur zurückgibt, flache sie ab
                # z.B. {"interview_data": {...}, "system_analyse": {...}, "empfehlungen": {...}}
                flattened = {}
                for key, value in parsed.items():
                    if isinstance(value, dict):
                        # Verschachteltes Dict - alle Felder übernehmen
                        for sub_key, sub_value in value.items():
                            if sub_key not in flattened:
                                flattened[sub_key] = sub_value
                    elif isinstance(value, list):
                        # Liste direkt übernehmen
                        flattened[key] = value
                    else:
                        # Skalarer Wert direkt übernehmen
                        flattened[key] = value
                
                # Verwende abgeflachte Struktur wenn sie mehr Felder hat
                if len(flattened) > len(parsed):
                    print(f"📦 Struktur abgeflacht: {len(parsed)} -> {len(flattened)} Felder")
                    parsed = flattened
                
                print(f"✅ JSON erfolgreich geparst mit {len(parsed)} Feldern")
                print(f"📄 Felder im JSON: {list(parsed.keys())}")
                
                # Konvertiere alte Feldnamen für Rückwärtskompatibilität
                if 'fehlerquellen_risiken' in parsed and 'fehlerquellen' not in parsed:
                    parsed['fehlerquellen'] = parsed['fehlerquellen_risiken']
                if 'verbesserungsempfehlungen' in parsed and 'verbesserungsideen' not in parsed:
                    parsed['verbesserungsideen'] = parsed['verbesserungsempfehlungen']
                if 'schnittstellen_abhaengigkeiten' in parsed and 'stakeholder_schnittstellen' not in parsed:
                    parsed['stakeholder_schnittstellen'] = parsed['schnittstellen_abhaengigkeiten']
                if 'offene_punkte' in parsed and 'offene_fragen' not in parsed:
                    parsed['offene_fragen'] = parsed['offene_punkte']
                    
                return parsed

            print("⚠️  Kein JSON in LLM-Antwort gefunden - nutze Fallback")
            return self._fallback_processing(interviews)

        except Exception as e:
            print(f"⚠️  LLM-Verarbeitung fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_processing(interviews)

    def _format_interviews_for_llm(self, interviews: List[Dict[str, Any]]) -> str:
        """Formatiert alle Interviews für LLM-Verarbeitung - optimiert für bessere Extraktion"""
        parts = []

        for interview in interviews:
            role = interview.get('role_label', 'Unbekannt')
            parts.append(f"\n{'='*60}")
            parts.append(f"INTERVIEW MIT: {role}")
            parts.append(f"{'='*60}\n")

            answers = interview.get('answers', {})
            schema_fields = interview.get('schema_fields', {})

            # Intake-Fragen zuerst
            intake_questions = interview.get('intake_questions', [])
            if intake_questions:
                parts.append("--- ALLGEMEINE FRAGEN ---\n")
                for q in intake_questions:
                    q_id = q.get('id', '')
                    q_text = q.get('text', '')
                    answer = answers.get(q_id, '')
                    if answer and len(str(answer)) > 5:
                        parts.append(f"FRAGE: {q_text}")
                        parts.append(f"ANTWORT: {answer}\n")

            # Rollenspezifische Fragen
            role_questions = interview.get('role_questions', [])
            if role_questions:
                current_theme = None
                for q in role_questions:
                    field_id = q.get('field_id', '')
                    q_text = q.get('text', '')
                    theme = q.get('theme_name', '')
                    
                    # Theme-Header wenn sich das Thema ändert
                    if theme and theme != current_theme:
                        parts.append(f"\n--- {theme.upper()} ---\n")
                        current_theme = theme

                    # Hole Antwort - zuerst aus schema_fields, dann aus answers
                    answer = None
                    if field_id in schema_fields:
                        field_data = schema_fields[field_id]
                        if isinstance(field_data, dict):
                            answer = field_data.get('raw_answer', field_data.get('value', ''))
                        elif isinstance(field_data, list):
                            answer = ', '.join(str(item) for item in field_data)
                        else:
                            answer = str(field_data)
                    
                    # Fallback: Suche in answers mit schema_ prefix
                    if not answer:
                        answer_key = f"schema_{field_id}"
                        answer = answers.get(answer_key, answers.get(q.get('id', ''), ''))

                    if answer and len(str(answer)) > 5:
                        parts.append(f"FRAGE: {q_text}")
                        parts.append(f"ANTWORT: {answer}\n")

            # Zusätzlich: Alle schema_fields die noch nicht erfasst wurden
            if schema_fields:
                uncaptured = []
                for field_id, field_data in schema_fields.items():
                    if isinstance(field_data, dict):
                        value = field_data.get('raw_answer', field_data.get('value', ''))
                    elif isinstance(field_data, list):
                        value = ', '.join(str(item) for item in field_data)
                    else:
                        value = str(field_data)
                    
                    if value and len(str(value)) > 10:
                        # Prüfe ob bereits in den Fragen erfasst
                        already_captured = any(
                            q.get('field_id') == field_id for q in role_questions
                        )
                        if not already_captured:
                            uncaptured.append(f"{field_id}: {value}")
                
                if uncaptured:
                    parts.append("\n--- WEITERE ERFASSTE INFORMATIONEN ---\n")
                    for item in uncaptured:
                        parts.append(item + "\n")

        result = "\n".join(parts)
        print(f"📋 Formatierte Interview-Daten: {len(result)} Zeichen, {len(interviews)} Interviews")
        return result
    
    def _fallback_processing(self, interviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Verbesserte Fallback-Verarbeitung wenn LLM nicht verfügbar.
        Extrahiert und strukturiert alle vorhandenen Informationen aus den Interviews.
        """
        print("📋 Nutze Fallback-Verarbeitung für Interview-Daten")
        
        roles = []
        all_text_parts = []
        systems = []
        problems = []
        goals = []
        improvements = []
        compliance = []
        stakeholders = []
        
        for interview in interviews:
            role = interview.get('role_label', '')
            if role:
                roles.append(role)

            answers = interview.get('answers', {})
            schema_fields = interview.get('schema_fields', {})
            
            # Sammle alle Antworten als Text (nur die Antworten, ohne Keys für Extraktion)
            for key, answer in answers.items():
                if isinstance(answer, str) and len(answer) > 20:
                    all_text_parts.append(answer)
            
            for key, field_data in schema_fields.items():
                value = None
                if isinstance(field_data, str) and len(field_data) > 20:
                    value = field_data
                elif isinstance(field_data, dict):
                    value = field_data.get('raw_answer', field_data.get('value', ''))
                elif isinstance(field_data, list):
                    value = ', '.join(str(item) for item in field_data if item)
                
                if value and len(str(value)) > 20:
                    all_text_parts.append(str(value))
        
        # Kombiniere alle Texte für Analyse
        full_text = "\n".join(all_text_parts)
        
        # Extrahiere Informationen basierend auf Keywords
        def extract_sentences(text: str, keywords: List[str], max_items: int = 10) -> List[str]:
            """Extrahiert Sätze die Keywords enthalten"""
            results = []
            # Teile in Sätze auf
            sentences = []
            for part in text.split('\n'):
                sentences.extend(part.split('.'))
            
            text_lower = text.lower()
            
            for kw in keywords:
                if kw.lower() in text_lower:
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if kw.lower() in sentence.lower() and len(sentence) > 30:
                            # Bereinige den Satz
                            clean = sentence
                            # Entferne [key]: Prefixe falls vorhanden
                            if clean.startswith('[') and ']:' in clean:
                                clean = clean.split(']:')[1].strip()
                            if clean and clean not in results and len(clean) > 20:
                                results.append(clean[:300])
                                if len(results) >= max_items:
                                    return results
            return results
        
        # Systeme & Tools
        system_keywords = ['system', 'software', 'tool', 'excel', 'sap', 'erp', 'mes', 
                          'vmware', 'azure', 'server', 'datenbank', 'sql', 'sharepoint',
                          'active directory', 'grafana', 'zabbix', 'backup', 'firewall',
                          'netzwerk', 'cloud', 'linux', 'windows']
        systems = extract_sentences(full_text, system_keywords, 12)
        
        # Probleme & Herausforderungen
        problem_keywords = ['problem', 'schwierig', 'fehler', 'manuell', 'veraltet', 
                           'herausforderung', 'ausfall', 'langsam', 'zeitaufwendig',
                           'risiko', 'mangel', 'lückenhaft', 'fragil', 'kritisch']
        problems = extract_sentences(full_text, problem_keywords, 10)
        
        # Ziele
        goal_keywords = ['ziel', 'möchte', 'soll', 'verbesser', 'optimier', 'modernisier',
                        'reduktion', 'gewährleist', 'erreichen', 'anstreben']
        goals = extract_sentences(full_text, goal_keywords, 8)
        
        # Verbesserungsideen & Automatisierung
        improvement_keywords = ['automatisier', 'verbessern', 'lösung', 'modern', 'cloud',
                               'optimier', 'effizienz', 'reduzier', 'schneller']
        improvements = extract_sentences(full_text, improvement_keywords, 8)
        
        # Compliance
        compliance_keywords = ['dsgvo', 'compliance', 'datenschutz', 'iso', 'audit',
                              'sicherheit', 'verschlüssel', 'anforderung', 'vorschrift']
        compliance = extract_sentences(full_text, compliance_keywords, 6)
        
        # Zusammenarbeit & Stakeholder
        stakeholder_keywords = ['zusammenarbeit', 'team', 'abteilung', 'partner', 
                               'schnittstelle', 'koordin', 'abstimm', 'kommunikation']
        stakeholders = extract_sentences(full_text, stakeholder_keywords, 6)
        
        # Baue Zusammenfassung
        summary_parts = []
        if roles:
            summary_parts.append(f"Basierend auf {len(interviews)} Interview(s) mit {', '.join(roles)}.")
        if problems:
            summary_parts.append(f"Es wurden {len(problems)} Problemfelder identifiziert.")
        if systems:
            summary_parts.append(f"Die IT-Landschaft umfasst diverse Systeme und Tools.")
        if goals:
            summary_parts.append(f"Zentrale Ziele umfassen Modernisierung und Optimierung.")
        
        executive_summary = " ".join(summary_parts) if summary_parts else "Zusammenfassung der Interview-Daten."
        
        # Ist-Situation aus ersten Antworten rekonstruieren
        ist_situation_parts = []
        for part in all_text_parts[:5]:
            if len(part) > 50:
                # Nimm die ersten 200 Zeichen jeder Antwort
                ist_situation_parts.append(part[:200])
        ist_situation = " ".join(ist_situation_parts)[:800] if ist_situation_parts else ""
        
        # Fazit generieren
        fazit = f"Die Analyse zeigt {len(problems)} identifizierte Problemfelder und {len(improvements)} potenzielle Verbesserungsmöglichkeiten. "
        if problems:
            fazit += "Hauptthemen sind: " + ", ".join([p[:50] + "..." for p in problems[:3]]) + ". "
        fazit += "Für eine detailliertere Analyse wird die LLM-Verarbeitung empfohlen."
        
        return {
            "prozessname": f"IT-Infrastruktur & Prozessanalyse" if 'it' in str(roles).lower() else "Prozessdokumentation",
            "executive_summary": executive_summary,
            "kurzbeschreibung": executive_summary,
            "ist_situation": ist_situation,
            "beteiligte_rollen": [f"{r}: Befragter Stakeholder" for r in roles] if roles else ["Keine Rollen spezifiziert"],
            "genutzte_systeme": systems if systems else ["Systeminformationen wurden erfasst - Details siehe Anhang"],
            "prozessziele": goals if goals else ["Ziele wurden im Interview erfasst - Details siehe Anhang"],
            "hauptprobleme": problems if problems else ["Problemfelder wurden erfasst - Details siehe Anhang"],
            "prozessschritte": [],
            "prozessablauf_beschreibung": ist_situation[:500] if ist_situation else "",
            "eingaben": [],
            "ausgaben": [],
            "entscheidungspunkte": [],
            "varianten_sonderfaelle": [],
            "automatisierungspotenziale": improvements if improvements else [],
            "fehlerquellen": [p for p in problems if 'fehler' in p.lower() or 'risiko' in p.lower()][:5],
            "verbesserungsideen": improvements,
            "verbesserungsempfehlungen": improvements,
            "quick_wins": [i for i in improvements if 'automatisier' in i.lower() or 'schnell' in i.lower()][:3],
            "strategische_massnahmen": [i for i in improvements if 'modern' in i.lower() or 'cloud' in i.lower()][:3],
            "zusatzinfos": "Diese Dokumentation wurde ohne LLM-Analyse erstellt. Alle Informationen wurden direkt aus den Interview-Antworten extrahiert.",
            "offene_fragen": [],
            "offene_punkte": [],
            "kennzahlen_metriken": extract_sentences(full_text, ['prozent', 'stunde', 'tag', 'uptime', 'verfügbar', 'kpi', 'metrik'], 5),
            "compliance_anforderungen": compliance,
            "stakeholder_schnittstellen": stakeholders,
            "schnittstellen_abhaengigkeiten": stakeholders,
            "fazit": fazit
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
        """Abschnitt 1: Executive Summary & Überblick"""
        elements = []

        elements.append(Paragraph(
            "1. Executive Summary & Überblick",
            self.styles['section_header']
        ))

        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))

        # Prozessname
        elements.append(Paragraph("Prozess / Bereich", self.styles['body_bold']))
        prozessname = content.get('prozessname', 'Nicht spezifiziert')
        elements.append(Paragraph(prozessname, self.styles['body']))
        elements.append(Spacer(1, 0.3*cm))

        # Executive Summary - prominenter dargestellt
        elements.append(Paragraph("Management Summary", self.styles['subsection_header']))
        executive_summary = content.get('executive_summary', content.get('kurzbeschreibung', 'Nicht spezifiziert'))
        elements.append(Paragraph(executive_summary, self.styles['body']))
        elements.append(Spacer(1, 0.4*cm))

        # Ist-Situation
        ist_situation = content.get('ist_situation', '')
        if ist_situation:
            elements.append(Paragraph("Aktuelle Situation (Ist-Zustand)", self.styles['subsection_header']))
            elements.append(Paragraph(ist_situation, self.styles['body']))
            elements.append(Spacer(1, 0.4*cm))

        # Beteiligte Rollen
        elements.append(Paragraph("Beteiligte Rollen & Verantwortlichkeiten", self.styles['body_bold']))
        roles = content.get('beteiligte_rollen', [])
        if roles and len(roles) > 0:
            elements.append(self._create_bullet_list(roles))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        elements.append(Spacer(1, 0.2*cm))

        # Stakeholder & Schnittstellen
        stakeholder = content.get('stakeholder_schnittstellen', content.get('schnittstellen_abhaengigkeiten', []))
        if stakeholder and len(stakeholder) > 0:
            elements.append(Paragraph("Schnittstellen & Abhängigkeiten", self.styles['body_bold']))
            elements.append(self._create_bullet_list(stakeholder))
            elements.append(Spacer(1, 0.2*cm))

        # Genutzte Systeme
        elements.append(Paragraph("Genutzte Systeme & Tools", self.styles['body_bold']))
        systems = content.get('genutzte_systeme', [])
        if systems and len(systems) > 0:
            elements.append(self._create_bullet_list(systems))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        elements.append(Spacer(1, 0.2*cm))

        # Prozessziele
        elements.append(Paragraph("Prozessziele & Anforderungen", self.styles['body_bold']))
        goals = content.get('prozessziele', [])
        if goals and len(goals) > 0:
            elements.append(self._create_bullet_list(goals))
        else:
            elements.append(Paragraph("Nicht spezifiziert", self.styles['body']))
        elements.append(Spacer(1, 0.2*cm))

        # Kennzahlen & Metriken
        metriken = content.get('kennzahlen_metriken', [])
        if metriken and len(metriken) > 0:
            elements.append(Paragraph("Kennzahlen & Metriken", self.styles['body_bold']))
            elements.append(self._create_bullet_list(metriken))
            elements.append(Spacer(1, 0.2*cm))

        # Compliance-Anforderungen
        compliance = content.get('compliance_anforderungen', [])
        if compliance and len(compliance) > 0:
            elements.append(Paragraph("Compliance & Regulatorische Anforderungen", self.styles['body_bold']))
            elements.append(self._create_bullet_list(compliance))

        elements.append(Spacer(1, 0.5*cm))

        return elements    
    def _create_section_roles(
        self,
        content: Dict[str, Any],
        interviews: List[Dict[str, Any]]
    ) -> List:
        """Abschnitt 2: Probleme, Herausforderungen & Risiken - basierend auf LLM-Analyse"""
        elements = []

        elements.append(Paragraph(
            "2. Analyse: Probleme, Risiken & Herausforderungen",
            self.styles['section_header']
        ))

        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))

        # Hauptprobleme - detailliert aus LLM-Analyse
        problems = content.get('hauptprobleme', [])
        if problems and len(problems) > 0:
            elements.append(Paragraph("Identifizierte Hauptprobleme", self.styles['subsection_header']))
            for i, problem in enumerate(problems, 1):
                elements.append(Paragraph(f"<b>Problem {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(problem), self.styles['body']))
                elements.append(Spacer(1, 0.2*cm))
            elements.append(Spacer(1, 0.3*cm))
        
        # Fehlerquellen & Risiken
        errors = content.get('fehlerquellen', content.get('fehlerquellen_risiken', []))
        if errors and len(errors) > 0:
            elements.append(Paragraph("Fehlerquellen & Risiken", self.styles['subsection_header']))
            for i, error in enumerate(errors, 1):
                elements.append(Paragraph(f"<b>Risiko {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(error), self.styles['body']))
                elements.append(Spacer(1, 0.2*cm))
            elements.append(Spacer(1, 0.3*cm))

        # Offene Punkte
        offene = content.get('offene_fragen', content.get('offene_punkte', []))
        if offene and len(offene) > 0:
            elements.append(Paragraph("Offene Punkte & Klärungsbedarf", self.styles['subsection_header']))
            elements.append(self._create_bullet_list(offene))
            elements.append(Spacer(1, 0.3*cm))

        elements.append(Spacer(1, 0.5*cm))
        return elements
    
    def _create_section_process(self, content: Dict[str, Any]) -> List:
        """Abschnitt 3: Detaillierter Prozessablauf"""
        elements = []

        elements.append(Paragraph(
            "3. Prozessablauf & Arbeitsweise",
            self.styles['section_header']
        ))

        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))

        # Prozessablauf-Beschreibung (narrativ)
        prozessablauf = content.get('prozessablauf_beschreibung', '')
        if prozessablauf:
            elements.append(Paragraph("Prozessbeschreibung", self.styles['subsection_header']))
            elements.append(Paragraph(prozessablauf, self.styles['body']))
            elements.append(Spacer(1, 0.4*cm))

        # Prozessschritte
        steps = content.get('prozessschritte', [])
        if steps and len(steps) > 0:
            elements.append(Paragraph("Ablauf / Hauptschritte", self.styles['body_bold']))
            elements.append(self._create_numbered_list(steps))
            elements.append(Spacer(1, 0.3*cm))
        
        # Eingaben
        inputs = content.get('eingaben', [])
        if inputs and len(inputs) > 0:
            elements.append(Paragraph("Eingaben / Inputs", self.styles['body_bold']))
            elements.append(self._create_bullet_list(inputs))
            elements.append(Spacer(1, 0.2*cm))

        # Ausgaben
        outputs = content.get('ausgaben', [])
        if outputs and len(outputs) > 0:
            elements.append(Paragraph("Ausgaben / Outputs / Ergebnisse", self.styles['body_bold']))
            elements.append(self._create_bullet_list(outputs))
            elements.append(Spacer(1, 0.2*cm))

        # Entscheidungspunkte
        decisions = content.get('entscheidungspunkte', [])
        if decisions and len(decisions) > 0:
            elements.append(Paragraph("Wichtige Entscheidungspunkte", self.styles['subsection_header']))
            for i, decision in enumerate(decisions, 1):
                elements.append(Paragraph(f"<b>Entscheidung {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(decision), self.styles['body']))
                elements.append(Spacer(1, 0.15*cm))
            elements.append(Spacer(1, 0.2*cm))

        # Varianten & Sonderfälle
        variants = content.get('varianten_sonderfaelle', [])
        if variants and len(variants) > 0:
            elements.append(Paragraph("Varianten & Sonderfälle", self.styles['subsection_header']))
            for i, variant in enumerate(variants, 1):
                elements.append(Paragraph(f"<b>Variante {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(variant), self.styles['body']))
                elements.append(Spacer(1, 0.15*cm))

        elements.append(Spacer(1, 0.5*cm))

        return elements
    
    def _create_section_potentials(self, content: Dict[str, Any]) -> List:
        """Abschnitt 4: Handlungsempfehlungen & Verbesserungspotenziale"""
        elements = []

        elements.append(Paragraph(
            "4. Handlungsempfehlungen & Verbesserungspotenziale",
            self.styles['section_header']
        ))

        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))

        # Quick Wins
        quick_wins = content.get('quick_wins', [])
        if quick_wins and len(quick_wins) > 0:
            elements.append(Paragraph("Quick Wins - Schnell umsetzbare Verbesserungen", self.styles['subsection_header']))
            for i, win in enumerate(quick_wins, 1):
                elements.append(Paragraph(f"<b>Quick Win {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(win), self.styles['body']))
                elements.append(Spacer(1, 0.15*cm))
            elements.append(Spacer(1, 0.3*cm))

        # Automatisierungspotenziale
        automation = content.get('automatisierungspotenziale', [])
        if automation and len(automation) > 0:
            elements.append(Paragraph("Automatisierungspotenziale", self.styles['subsection_header']))
            for i, auto in enumerate(automation, 1):
                elements.append(Paragraph(f"<b>Potenzial {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(auto), self.styles['body']))
                elements.append(Spacer(1, 0.15*cm))
            elements.append(Spacer(1, 0.3*cm))

        # Verbesserungsempfehlungen
        ideas = content.get('verbesserungsideen', content.get('verbesserungsempfehlungen', []))
        if ideas and len(ideas) > 0:
            elements.append(Paragraph("Verbesserungsempfehlungen", self.styles['subsection_header']))
            for i, idea in enumerate(ideas, 1):
                elements.append(Paragraph(f"<b>Empfehlung {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(idea), self.styles['body']))
                elements.append(Spacer(1, 0.15*cm))
            elements.append(Spacer(1, 0.3*cm))

        # Strategische Maßnahmen
        strategic = content.get('strategische_massnahmen', [])
        if strategic and len(strategic) > 0:
            elements.append(Paragraph("Strategische Maßnahmen (längerfristig)", self.styles['subsection_header']))
            for i, measure in enumerate(strategic, 1):
                elements.append(Paragraph(f"<b>Maßnahme {i}:</b>", self.styles['body_bold']))
                elements.append(Paragraph(str(measure), self.styles['body']))
                elements.append(Spacer(1, 0.15*cm))

        elements.append(Spacer(1, 0.5*cm))

        return elements
    
    def _create_section_additional(self, content: Dict[str, Any]) -> List:
        """Abschnitt 5: Fazit & Gesamtbewertung"""
        elements = []
        
        elements.append(Paragraph(
            "5. Fazit & Gesamtbewertung",
            self.styles['section_header']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#bdc3c7')
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Fazit
        fazit = content.get('fazit', '')
        if fazit:
            elements.append(Paragraph("Gesamteinschätzung", self.styles['subsection_header']))
            elements.append(Paragraph(fazit, self.styles['body']))
            elements.append(Spacer(1, 0.4*cm))
        
        # Zusatzinformationen
        additional = content.get('zusatzinfos', '')
        if additional and additional != "Fallback-Verarbeitung - für detailliertere Analyse LLM-Verarbeitung aktivieren":
            elements.append(Paragraph("Ergänzende Informationen", self.styles['body_bold']))
            elements.append(Paragraph(additional, self.styles['body']))
            elements.append(Spacer(1, 0.3*cm))
        
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
