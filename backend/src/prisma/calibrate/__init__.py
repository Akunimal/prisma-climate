"""Calibration methods (EMOS / quantile mapping) per docs/EVALUATION_PROTOCOL.md.

Code and unit tests only; nothing here writes to results/ or computes a
published skill number (15-issue-date gate).
"""

from .emos import EmosParams, crps_gaussian, fit_emos_gaussian, predict_emos
from .quantile_mapping import QuantileMapping, fit_quantile_mapping

__all__ = [
    "EmosParams",
    "QuantileMapping",
    "crps_gaussian",
    "fit_emos_gaussian",
    "fit_quantile_mapping",
    "predict_emos",
]
