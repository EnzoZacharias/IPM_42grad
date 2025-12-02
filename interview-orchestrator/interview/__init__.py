"""
Interview-Modul für den Interview-Orchestrator.
Enthält Engine, Fragengenerierung und Schema-Management.
"""

from interview.engine import InterviewEngine, PHASE_INTAKE, PHASE_ROLE
from interview.repo import QuestionRepo
from interview.role_classifier import RoleClassifier
from interview.question_generator import DynamicQuestionGenerator
from interview.role_schema_manager import RoleSchemaManager, get_schema_manager

__all__ = [
    "InterviewEngine",
    "PHASE_INTAKE",
    "PHASE_ROLE",
    "QuestionRepo",
    "RoleClassifier",
    "DynamicQuestionGenerator",
    "RoleSchemaManager",
    "get_schema_manager"
]
