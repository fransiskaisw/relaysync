"""Transfer Quality 0 sampai 100 untuk satu percobaan."""
from __future__ import annotations

from dataclasses import dataclass

SCORE_MIN = 0.0
SCORE_MAX = 100.0


@dataclass(frozen=True, slots=True)
class ScoreRules:
    start: float
    gap_target_m: float
    gap_penalty_per_m: float
    speed_penalty_per_mps: float
    alert_penalty: float
    clean_bonus: float


def transfer_quality(gap_m: float, v1_mps: float, v2_mps: float, alert_count: int,
                     rules: ScoreRules) -> float:
    """Mulai dari start, kurangi simpangan gap, selisih kecepatan, dan alert."""
    score = rules.start
    score -= rules.gap_penalty_per_m * abs(gap_m - rules.gap_target_m)
    score -= rules.speed_penalty_per_mps * abs(v1_mps - v2_mps)
    score -= rules.alert_penalty * alert_count
    if alert_count == 0:
        score += rules.clean_bonus
    return max(SCORE_MIN, min(SCORE_MAX, score))
