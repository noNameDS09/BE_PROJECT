from loupe.orchestrators.base import Orchestrator, RunContext
from loupe.orchestrators.loupe import ABLATIONS, LoupeOrch
from loupe.orchestrators.plan_execute import PlanExecute
from loupe.orchestrators.react import ReAct
from loupe.orchestrators.router import Router
from loupe.orchestrators.self_refine import SelfRefine
from loupe.orchestrators.simple import ClosedBook, SingleShotRAG

MAIN_ARMS: list[Orchestrator] = [
    ClosedBook(),
    SingleShotRAG(),
    ReAct(),
    PlanExecute(),
    Router(),
    SelfRefine(),
    LoupeOrch(),
]
ARMS: dict[str, Orchestrator] = {a.name: a for a in MAIN_ARMS} | ABLATIONS

__all__ = ["ARMS", "MAIN_ARMS", "Orchestrator", "RunContext"]
