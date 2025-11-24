from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class StartRequest(BaseModel):
    role_hint: Optional[str] = Field(default=None, description="Optionaler erster Rollenhinweis")

class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    value: Any

class GapRequest(BaseModel):
    role: str
    answers: Dict[str, Any]
    required_ids: List[str]

class DocRequest(BaseModel):
    session_id: str
    target: str = "it"
    polish: bool = False