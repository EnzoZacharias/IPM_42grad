import json
from typing import Dict, List, Any

class QuestionRepo:
    def __init__(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = json.load(f)

    def universal(self) -> List[Dict[str, Any]]:
        return list(self.config.get("universal_questions", []))

    def by_role(self, role: str) -> List[Dict[str, Any]]:
        return list(self.config.get("role_questions", {}).get(role, []))

    def discriminators(self) -> List[Dict[str, Any]]:
        return list(self.config.get("discriminators", []))

    def roles(self) -> List[str]:
        return list(self.config.get("roles", []))