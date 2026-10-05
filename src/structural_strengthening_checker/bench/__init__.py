"""内置基准（M4 达标）：验算真值比对 + 方案核查对账。"""

from .calc_bench import load_cases, run_calc_bench
from .check_bench import (
    MAX_FALSE_POSITIVES,
    REQUIRED_DETECTION_RATE,
    REQUIRED_VERDICT_ACCURACY,
    reconcile_doc,
    run_check_bench,
    thresholds_met,
)

__all__ = [
    "load_cases",
    "run_calc_bench",
    "run_check_bench",
    "reconcile_doc",
    "thresholds_met",
    "REQUIRED_DETECTION_RATE",
    "MAX_FALSE_POSITIVES",
    "REQUIRED_VERDICT_ACCURACY",
]
