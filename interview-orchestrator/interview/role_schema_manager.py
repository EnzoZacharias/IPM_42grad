"""
Role Schema Manager - Verwaltet rollenspezifische Fragebogen-Schemas
und trackt den Fortschritt im Interview.
"""
import json
import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path


class RoleSchemaManager:
    """
    Verwaltet die rollenspezifischen Fragebogen-Schemas und trackt
    welche Felder bereits beantwortet wurden.
    """
    
    def __init__(self, config_dir: str = None):
        """
        Initialisiert den Schema Manager.
        
        Args:
            config_dir: Pfad zum config-Verzeichnis mit den Schema-Dateien
        """
        if config_dir is None:
            # Standard: config-Verzeichnis relativ zu diesem Modul
            config_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config"
            )
        self.config_dir = config_dir
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Lädt alle Role-Schema-Dateien aus dem config-Verzeichnis."""
        schema_files = {
            "fach": "role_schema_fach.json",
            "it": "role_schema_it.json",
            "management": "role_schema_management.json"
        }
        
        for role, filename in schema_files.items():
            filepath = os.path.join(self.config_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    self.schemas[role] = json.load(f)
                print(f"✅ Schema für Rolle '{role}' geladen: {filename}")
            else:
                print(f"⚠️  Schema-Datei nicht gefunden: {filepath}")
    
    def get_schema(self, role: str) -> Optional[Dict[str, Any]]:
        """Gibt das Schema für eine bestimmte Rolle zurück."""
        return self.schemas.get(role)
    
    def get_all_fields(self, role: str) -> Dict[str, Dict[str, Any]]:
        """
        Gibt alle Felder für eine Rolle als flaches Dictionary zurück.
        
        Returns:
            Dict mit field_id -> field_definition
        """
        schema = self.get_schema(role)
        if not schema:
            return {}
        
        all_fields = {}
        for theme_id, theme_data in schema.get("fields", {}).items():
            for field_id, field_def in theme_data.get("fields", {}).items():
                # Füge Theme-Info hinzu
                field_def_copy = field_def.copy()
                field_def_copy["theme_id"] = theme_id
                field_def_copy["theme_name"] = theme_data.get("name", theme_id)
                all_fields[field_id] = field_def_copy
        
        return all_fields
    
    def get_required_fields(self, role: str) -> List[str]:
        """Gibt Liste aller erforderlichen Feld-IDs zurück."""
        all_fields = self.get_all_fields(role)
        return [
            field_id for field_id, field_def in all_fields.items()
            if field_def.get("required", False) and not field_def.get("conditional")
        ]
    
    def get_conditional_fields(self, role: str) -> Dict[str, str]:
        """
        Gibt Dictionary mit bedingten Feldern zurück.
        
        Returns:
            Dict mit field_id -> condition_string
        """
        all_fields = self.get_all_fields(role)
        return {
            field_id: field_def.get("conditional")
            for field_id, field_def in all_fields.items()
            if field_def.get("conditional")
        }
    
    def calculate_progress(
        self, 
        role: str, 
        filled_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Berechnet den Fortschritt für eine Rolle basierend auf den gefüllten Feldern.
        
        Args:
            role: Die Rolle (fach, it, management)
            filled_fields: Dictionary mit bereits beantworteten Feldern
            
        Returns:
            Dictionary mit Fortschritts-Informationen:
            - total_fields: Gesamtzahl der Felder
            - required_fields: Anzahl der Pflichtfelder
            - filled_fields: Anzahl der ausgefüllten Felder
            - filled_required: Anzahl der ausgefüllten Pflichtfelder
            - progress_percent: Fortschritt in Prozent (basierend auf Pflichtfeldern)
            - missing_required: Liste der fehlenden Pflichtfelder
            - themes_progress: Fortschritt pro Themenfeld
            - is_complete: Boolean ob alle Pflichtfelder ausgefüllt sind
        """
        schema = self.get_schema(role)
        if not schema:
            return {
                "total_fields": 0,
                "required_fields": 0,
                "filled_fields": 0,
                "filled_required": 0,
                "progress_percent": 0,
                "missing_required": [],
                "themes_progress": {},
                "is_complete": False
            }
        
        all_fields = self.get_all_fields(role)
        required_fields = self.get_required_fields(role)
        conditional_fields = self.get_conditional_fields(role)
        
        # Zähle ausgefüllte Felder
        filled_count = 0
        filled_required_count = 0
        missing_required = []
        
        for field_id in all_fields:
            is_filled = field_id in filled_fields and filled_fields[field_id]
            
            if is_filled:
                filled_count += 1
                if field_id in required_fields:
                    filled_required_count += 1
            else:
                if field_id in required_fields:
                    missing_required.append(field_id)
        
        # Prüfe bedingte Felder
        active_conditional_required = []
        for field_id, condition in conditional_fields.items():
            if self._evaluate_condition(condition, filled_fields):
                if all_fields[field_id].get("required", False):
                    active_conditional_required.append(field_id)
                    if field_id not in filled_fields or not filled_fields[field_id]:
                        missing_required.append(field_id)
        
        # Berechne Fortschritt pro Theme
        themes_progress = {}
        for theme_id, theme_data in schema.get("fields", {}).items():
            theme_fields = theme_data.get("fields", {})
            theme_filled = sum(
                1 for f_id in theme_fields 
                if f_id in filled_fields and filled_fields[f_id]
            )
            theme_required = sum(
                1 for f_id, f_def in theme_fields.items()
                if f_def.get("required", False) and not f_def.get("conditional")
            )
            theme_required_filled = sum(
                1 for f_id, f_def in theme_fields.items()
                if f_def.get("required", False) 
                and not f_def.get("conditional")
                and f_id in filled_fields 
                and filled_fields[f_id]
            )
            
            themes_progress[theme_id] = {
                "name": theme_data.get("name", theme_id),
                "total": len(theme_fields),
                "filled": theme_filled,
                "required": theme_required,
                "required_filled": theme_required_filled,
                "progress_percent": (
                    round(theme_required_filled / theme_required * 100, 1)
                    if theme_required > 0 else 100
                )
            }
        
        # Gesamtfortschritt basierend auf Pflichtfeldern
        total_required = len(required_fields) + len(active_conditional_required)
        progress_percent = (
            round(filled_required_count / total_required * 100, 1)
            if total_required > 0 else 100
        )
        
        # Prüfe Completion-Kriterien
        completion_criteria = schema.get("completion_criteria", {})
        min_required = completion_criteria.get("minimum_required_fields", 0)
        required_themes = completion_criteria.get("required_themes", [])
        
        is_complete = (
            filled_required_count >= min_required
            and len(missing_required) == 0
            and all(
                themes_progress.get(theme, {}).get("required_filled", 0) > 0
                for theme in required_themes
            )
        )
        
        return {
            "total_fields": len(all_fields),
            "required_fields": total_required,
            "filled_fields": filled_count,
            "filled_required": filled_required_count,
            "progress_percent": progress_percent,
            "missing_required": missing_required,
            "themes_progress": themes_progress,
            "is_complete": is_complete
        }
    
    def _evaluate_condition(
        self, 
        condition: str, 
        filled_fields: Dict[str, Any]
    ) -> bool:
        """
        Evaluiert eine Bedingung für ein bedingtes Feld.
        
        Unterstützte Formate:
        - "field_id == 'value'"
        - "field_id >= 3"
        - "field_id contains 'value'"
        """
        if not condition:
            return False
        
        # Parsen der Bedingung
        if " contains " in condition:
            parts = condition.split(" contains ")
            field_id = parts[0].strip()
            value = parts[1].strip().strip("'\"")
            field_value = filled_fields.get(field_id, "")
            if isinstance(field_value, list):
                return value in field_value
            return value in str(field_value)
        
        elif " >= " in condition:
            parts = condition.split(" >= ")
            field_id = parts[0].strip()
            threshold = int(parts[1].strip())
            field_value = filled_fields.get(field_id, 0)
            try:
                return int(field_value) >= threshold
            except (ValueError, TypeError):
                return False
        
        elif " == " in condition:
            parts = condition.split(" == ")
            field_id = parts[0].strip()
            expected = parts[1].strip().strip("'\"")
            return str(filled_fields.get(field_id, "")) == expected
        
        elif " < " in condition:
            parts = condition.split(" < ")
            field_id = parts[0].strip()
            threshold = int(parts[1].strip())
            field_value = filled_fields.get(field_id, 0)
            try:
                return int(field_value) < threshold
            except (ValueError, TypeError):
                return False
        
        return False
    
    def get_next_unanswered_field(
        self, 
        role: str, 
        filled_fields: Dict[str, Any]
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Gibt das nächste unbeantwortete Pflichtfeld zurück.
        
        Returns:
            Tuple (field_id, field_definition) oder None
        """
        schema = self.get_schema(role)
        if not schema:
            return None
        
        # Iteriere durch Themen in Reihenfolge
        for theme_id, theme_data in schema.get("fields", {}).items():
            for field_id, field_def in theme_data.get("fields", {}).items():
                # Überspringe bereits beantwortete
                if field_id in filled_fields and filled_fields[field_id]:
                    continue
                
                # Überspringe nicht-erforderliche bei erster Iteration
                if not field_def.get("required", False):
                    continue
                
                # Prüfe bedingte Felder
                condition = field_def.get("conditional")
                if condition and not self._evaluate_condition(condition, filled_fields):
                    continue
                
                # Füge Theme-Info hinzu
                field_def_with_context = field_def.copy()
                field_def_with_context["theme_id"] = theme_id
                field_def_with_context["theme_name"] = theme_data.get("name", theme_id)
                field_def_with_context["field_id"] = field_id
                
                return (field_id, field_def_with_context)
        
        return None
    
    def map_answer_to_fields(
        self,
        role: str,
        answer: str,
        current_question: Dict[str, Any],
        filled_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Versucht, eine Antwort mehreren Feldern zuzuordnen.
        
        Eine Antwort kann bei Bedarf mehrere JSON-Felder füllen,
        wenn sie relevante Informationen zu verschiedenen Aspekten enthält.
        
        Args:
            role: Die aktuelle Rolle
            answer: Die Antwort des Nutzers
            current_question: Die aktuelle Frage
            filled_fields: Bereits ausgefüllte Felder
            
        Returns:
            Dictionary mit den aktualisierten/neuen Feldwerten
        """
        updates = {}
        
        # Das Hauptfeld der aktuellen Frage
        field_id = current_question.get("field_id")
        if field_id:
            updates[field_id] = answer
        
        # Hier könnte später eine LLM-basierte Extraktion hinzugefügt werden,
        # um zusätzliche Felder aus einer umfangreichen Antwort zu extrahieren
        
        return updates
    
    def get_progress_display(
        self, 
        role: str, 
        filled_fields: Dict[str, Any]
    ) -> str:
        """
        Erzeugt eine lesbare Fortschrittsanzeige.
        
        Returns:
            Formatierter String mit Fortschritts-Balken und Details
        """
        progress = self.calculate_progress(role, filled_fields)
        
        schema = self.get_schema(role)
        role_name = schema.get("role_name", role) if schema else role
        
        # Progress-Balken
        bar_length = 20
        filled_bars = int(progress["progress_percent"] / 100 * bar_length)
        progress_bar = "█" * filled_bars + "░" * (bar_length - filled_bars)
        
        lines = [
            f"\n{'='*50}",
            f"📊 Interview-Fortschritt: {role_name}",
            f"{'='*50}",
            f"",
            f"[{progress_bar}] {progress['progress_percent']}%",
            f"",
            f"📝 Ausgefüllte Felder: {progress['filled_fields']}/{progress['total_fields']}",
            f"✅ Pflichtfelder: {progress['filled_required']}/{progress['required_fields']}",
            f""
        ]
        
        # Themen-Details
        lines.append("Themenfelder:")
        for theme_id, theme_progress in progress["themes_progress"].items():
            status = "✅" if theme_progress["required_filled"] == theme_progress["required"] else "⏳"
            lines.append(
                f"  {status} {theme_progress['name']}: "
                f"{theme_progress['required_filled']}/{theme_progress['required']} Pflichtfelder"
            )
        
        if progress["is_complete"]:
            lines.append(f"\n🎉 Interview für Rolle '{role_name}' abgeschlossen!")
        else:
            lines.append(f"\n⏳ Noch {len(progress['missing_required'])} Pflichtfelder offen")
        
        lines.append(f"{'='*50}\n")
        
        return "\n".join(lines)
    
    def get_themes_list(self, role: str) -> List[Dict[str, Any]]:
        """Gibt Liste der Themenfelder für eine Rolle zurück."""
        schema = self.get_schema(role)
        if not schema:
            return []
        
        themes = []
        for theme_id, theme_data in schema.get("fields", {}).items():
            field_count = len(theme_data.get("fields", {}))
            required_count = sum(
                1 for f in theme_data.get("fields", {}).values()
                if f.get("required", False)
            )
            themes.append({
                "id": theme_id,
                "name": theme_data.get("name", theme_id),
                "field_count": field_count,
                "required_count": required_count
            })
        
        return themes


# Singleton-Instanz für einfachen Zugriff
_schema_manager: Optional[RoleSchemaManager] = None


def get_schema_manager() -> RoleSchemaManager:
    """Gibt die Singleton-Instanz des Schema Managers zurück."""
    global _schema_manager
    if _schema_manager is None:
        _schema_manager = RoleSchemaManager()
    return _schema_manager
