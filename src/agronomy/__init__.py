"""
src/agronomy/__init__.py
Agronomy package: RAG evidence store, statutory safety guardrails, and LLM/VLM providers.
"""
from src.agronomy.knowledge_store import InMemoryKnowledgeStore, KnowledgeStore
from src.agronomy.prescription import (
    DISCLAIMER,
    create_chemical_prescription,
    get_herbicide_prescription,
)
from src.agronomy.prescription_schema import ChemicalPrescription, CitationRecord
from src.agronomy.provider_contract import (
    BaseAgronomyProvider,
    LLMRequest,
    LLMResponse,
)
from src.agronomy.providers import HostedGroqProvider, LocalQwenProvider
from src.agronomy.system2_node import System2Reasoner
from src.agronomy.vlm_critic import VLMCritic, VLMDiagnosis, parse_json

__all__ = [
    "KnowledgeStore",
    "InMemoryKnowledgeStore",
    "get_herbicide_prescription",
    "create_chemical_prescription",
    "DISCLAIMER",
    "ChemicalPrescription",
    "CitationRecord",
    "BaseAgronomyProvider",
    "LLMRequest",
    "LLMResponse",
    "LocalQwenProvider",
    "HostedGroqProvider",
    "VLMCritic",
    "VLMDiagnosis",
    "parse_json",
    "System2Reasoner",
]
