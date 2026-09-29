"""
Stream C: Deterministic Compute
- Pledge percentage, RPT ratios, results ratios
- Distress early-warning score
- Rumour-verification price window
- Lakh/crore and IndAS unit handling
"""

from .pledge import compute_pledge_percentage
from .rpt import compute_rpt_ratios
from .results import compute_results_ratios
from .distress import compute_distress_score
from .rumour import verify_rumour
from .units import normalize_amount, parse_indian_number
from .models import ComputeResult, Ratio, DistressSignal

__all__ = [
    "compute_pledge_percentage",
    "compute_rpt_ratios",
    "compute_results_ratios",
    "compute_distress_score",
    "verify_rumour",
    "normalize_amount",
    "parse_indian_number",
    "ComputeResult",
    "Ratio",
    "DistressSignal",
]