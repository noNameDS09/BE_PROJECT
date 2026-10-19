from loupe.orchestrators.base import Orchestrator, RunContext
from loupe.orchestrators.react import ReAct
from loupe.orchestrators.simple import ClosedBook, SingleShotRAG

ARMS: dict[str, Orchestrator] = {a.name: a for a in (ClosedBook(), SingleShotRAG(), ReAct())}

__all__ = ["ARMS", "Orchestrator", "RunContext"]
