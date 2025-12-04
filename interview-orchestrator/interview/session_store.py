"""
Session Store - Persistente Speicherung von Interview-Sessions.
Ermöglicht das Fortsetzen eines Interviews nach Neustart der Anwendung.
"""
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Verwaltet die persistente Speicherung von Interview-Sessions.
    Sessions werden als JSON-Dateien gespeichert.
    """
    
    def __init__(self, storage_dir: str = None):
        """
        Initialisiert den Session Store.
        
        Args:
            storage_dir: Verzeichnis für Session-Dateien (Standard: sessions/)
        """
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "sessions"
            )
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        logger.info(f"📁 Session Store initialisiert: {self.storage_dir}")
    
    def _get_session_path(self, session_id: str) -> str:
        """Gibt den Dateipfad für eine Session zurück."""
        # Bereinige Session-ID für Dateinamen
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "_-")
        return os.path.join(self.storage_dir, f"{safe_id}.json")
    
    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Speichert eine Session persistent.
        
        Args:
            session_id: Eindeutige Session-ID
            session_data: Die zu speichernden Session-Daten
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            # Erstelle speicherbare Kopie der Session-Daten
            saveable_data = self._prepare_for_storage(session_data)
            saveable_data['_meta'] = {
                'session_id': session_id,
                'saved_at': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            filepath = self._get_session_path(session_id)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(saveable_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Session gespeichert: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern der Session {session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Lädt eine gespeicherte Session.
        
        Args:
            session_id: Die Session-ID
            
        Returns:
            Session-Daten oder None wenn nicht gefunden
        """
        filepath = self._get_session_path(session_id)
        
        if not os.path.exists(filepath):
            logger.info(f"📂 Keine gespeicherte Session gefunden: {session_id}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Entferne Meta-Daten
            meta = data.pop('_meta', {})
            saved_at = meta.get('saved_at', 'unbekannt')
            
            logger.info(f"📂 Session geladen: {session_id} (gespeichert: {saved_at})")
            return data
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Session {session_id}: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Löscht eine gespeicherte Session.
        
        Args:
            session_id: Die Session-ID
            
        Returns:
            True bei Erfolg, False wenn nicht gefunden oder Fehler
        """
        filepath = self._get_session_path(session_id)
        
        if not os.path.exists(filepath):
            return False
        
        try:
            os.remove(filepath)
            logger.info(f"🗑️  Session gelöscht: {session_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Fehler beim Löschen der Session {session_id}: {e}")
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        Listet alle gespeicherten Sessions auf.
        
        Returns:
            Liste mit Session-Informationen
        """
        sessions = []
        
        if not os.path.exists(self.storage_dir):
            return sessions
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    meta = data.get('_meta', {})
                    session_id = meta.get('session_id', filename.replace('.json', ''))
                    saved_at = meta.get('saved_at')
                    
                    # Berechne Fortschritt falls Schema-Felder vorhanden
                    schema_fields = data.get('schema_fields', {})
                    progress_percent = None
                    if schema_fields:
                        filled = sum(1 for v in schema_fields.values() if v)
                        total = len(schema_fields)
                        if total > 0:
                            progress_percent = round((filled / total) * 100)
                    
                    # Rolle-Label
                    role = data.get('role')
                    role_label = {
                        'fachabteilung': 'Fachabteilung',
                        'it': 'IT',
                        'management': 'Management'
                    }.get(role, role)
                    
                    # Multi-Rollen-Info
                    completed_interviews = data.get('completed_interviews', [])
                    completed_roles = [i.get('role') for i in completed_interviews if i.get('role')]
                    completed_roles_labels = [{
                        'fachabteilung': 'Fachabteilung',
                        'it': 'IT',
                        'management': 'Management'
                    }.get(r, r) for r in completed_roles]
                    
                    # Session-Name: Verwende gespeicherten Namen oder generiere einen
                    session_name = data.get('session_name')
                    if not session_name:
                        # Generiere einen lesbaren Namen aus dem Datum
                        if saved_at:
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(saved_at.replace('Z', '+00:00'))
                                date_str = dt.strftime('%d.%m.%Y')
                                session_name = f"Interview vom {date_str}"
                            except:
                                session_name = f"Interview {session_id[:15]}"
                        else:
                            session_name = f"Interview {session_id[:15]}"
                    
                    sessions.append({
                        'session_id': session_id,
                        'session_name': session_name,
                        'saved_at': saved_at,
                        'last_activity': saved_at,  # Für Frontend-Kompatibilität
                        'phase': data.get('phase', 'unknown'),
                        'role': role_label,
                        'answered_questions': len(data.get('answers', {})),
                        'progress_percent': progress_percent,
                        'completed_interviews': len(completed_interviews),
                        'completed_roles': completed_roles_labels,
                        'filepath': filepath
                    })
                except Exception as e:
                    logger.warning(f"⚠️  Fehler beim Lesen von {filename}: {e}")
        
        # Sortiere nach Speicherdatum (neueste zuerst), handle None values
        sessions.sort(key=lambda x: x.get('saved_at') or '', reverse=True)
        
        return sessions
    
    def session_exists(self, session_id: str) -> bool:
        """Prüft ob eine Session existiert."""
        return os.path.exists(self._get_session_path(session_id))
    
    def _prepare_for_storage(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bereitet Session-Daten für die Speicherung vor.
        Entfernt nicht-serialisierbare Objekte.
        """
        # Erstelle tiefe Kopie nur der speicherbaren Daten
        saveable = {}
        
        # Wichtige Felder die gespeichert werden sollen
        saveable_keys = [
            'phase', 'answers', 'role', 'role_candidates',
            'classification_explanation', 'role_low_confidence',
            'intake_questions', 'role_questions', 'clarifying_questions',
            'schema_fields', 'uploaded_files', 'document_summary',
            'role_announced', 'session_name',
            # Multi-Rollen-Support
            'completed_interviews', 'current_interview_index'
        ]
        
        for key in saveable_keys:
            if key in session_data:
                value = session_data[key]
                # Konvertiere zu JSON-kompatiblem Format
                saveable[key] = self._make_serializable(value)
        
        return saveable
    
    def _make_serializable(self, obj: Any) -> Any:
        """Konvertiert ein Objekt in ein JSON-serialisierbares Format."""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        # Fallback: Versuche String-Konvertierung
        try:
            return str(obj)
        except:
            return None
    
    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        """
        Gibt die zuletzt gespeicherte Session zurück.
        
        Returns:
            Dict mit session_id und session_data oder None
        """
        sessions = self.list_sessions()
        if not sessions:
            return None
        
        latest = sessions[0]  # Bereits nach Datum sortiert
        session_data = self.load_session(latest['session_id'])
        
        if session_data:
            return {
                'session_id': latest['session_id'],
                'session_data': session_data,
                'info': latest
            }
        return None


# Singleton-Instanz
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Gibt die Singleton-Instanz des Session Stores zurück."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
