"""Test ranking. Never reads hidden ground truth; operates only on as-of-build decision contexts."""

from ee_ranking.baselines import rank_random, rank_severity
from ee_ranking.config import EngineeringWeights, RankingConfig, load_ranking_config
from ee_ranking.engineering import RankedTest, rank_engineering
from ee_ranking.features import FEATURE_NAMES, CandidateFeatures, DecisionContext, build_context
from ee_ranking.learned import DefectProbabilityModel, rank_hybrid, train_defect_model

STRATEGIES = ("risk_based", "hybrid", "severity_baseline", "random_baseline")

__all__ = [
    "FEATURE_NAMES",
    "STRATEGIES",
    "CandidateFeatures",
    "DecisionContext",
    "DefectProbabilityModel",
    "EngineeringWeights",
    "RankedTest",
    "RankingConfig",
    "build_context",
    "load_ranking_config",
    "rank_engineering",
    "rank_hybrid",
    "rank_random",
    "rank_severity",
    "train_defect_model",
]
