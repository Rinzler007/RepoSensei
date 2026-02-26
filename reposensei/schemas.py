from typing import List
from pydantic import BaseModel


class ModuleItem(BaseModel):
    name: str
    purpose: str
    key_files: List[str]


class FlowItem(BaseModel):
    name: str
    steps: List[str]


class RepoReport(BaseModel):
    repo_name: str
    tech_stack: List[str]
    overview: str
    module_map: List[ModuleItem]
    critical_flows: List[FlowItem]
    mermaid_diagram: str
    onboarding_path: List[str]
    improvements: List[str]