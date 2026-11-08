"""Search configuration for AutoRank Lab."""
from __future__ import annotations

from pathlib import Path

# Time-safe folds. Training labels are capped at the train end.
FOLDS = {
    "primary": {
        "train": ("2024-01", "2024-12"),
        "label_cap": "2024-12-31",
        "test": ("2025-01", "2025-09"),
    },
    "rolling": {
        "train": ("2024-07", "2025-03"),
        "label_cap": "2025-03-31",
        "test": ("2025-04", "2025-09"),
    },
    "confirmation": {
        "train": ("2024-01", "2024-09"),
        "label_cap": "2024-12-31",
        "test": ("2025-01", "2025-09"),
    },
}

# Feature groups. Banned fields are never included.
FEATURE_GROUPS = {
    "signals": ["epss_f", "exploitdb", "metasploit", "nuclei", "poc_github", "anyx", "nx"],
    "assigner": ["asg_rate", "asg_kev", "asg_kev_log", "asg_cves_log"],
    "assigner24": ["asg24_rate", "asg24_kev", "asg24_kev_log"],
    "text_tfidf": ["txt"],
    "text_granite": ["txt_granite"],
    "temporal": [
        "age_days",
        "month_idx",
        "month_volume",
        "same_day_count",
        "assigner_month_volume",
    ],
    "vector": ["vec_kev_rate", "vec_kev_count", "vec_sim_mean", "vec_sim_max"],
    "timeseries": ["ttm_kev_forecast", "ttm_volume_forecast", "ttm_ratio"],
}

# Model space. Keep it small: 40 honest positives cannot support deep tuning.
MODEL_SPACE = {
    "hgb": {
        "max_depth": [2, 3, 4],
        "learning_rate": [0.03, 0.05, 0.1],
        "max_iter": [100, 150, 300],
        "min_samples_leaf": [20, 40, 60],
        "l2_regularization": [0.0, 5.0, 20.0],
    },
    "lightgbm": {
        "num_leaves": [7, 15, 31],
        "learning_rate": [0.03, 0.05, 0.1],
        "n_estimators": [150, 300, 500],
        "min_child_samples": [20, 40, 60],
        "reg_lambda": [0.0, 5.0, 20.0],
    },
    "xgboost": {
        "max_depth": [2, 3, 4],
        "learning_rate": [0.03, 0.05, 0.1],
        "n_estimators": [150, 300, 500],
        "min_child_weight": [1, 5, 10],
        "reg_lambda": [1.0, 5.0, 20.0],
    },
    "catboost": {
        "depth": [2, 3, 4],
        "learning_rate": [0.03, 0.05, 0.1],
        "iterations": [150, 300, 500],
        "l2_leaf_reg": [1.0, 5.0, 20.0],
    },
    "random_forest": {
        "n_estimators": [200, 400],
        "max_depth": [5, 10, None],
        "min_samples_leaf": [5, 20],
        "max_features": ["sqrt", 0.3],
    },
    "extra_trees": {
        "n_estimators": [200, 400],
        "max_depth": [5, 10, None],
        "min_samples_leaf": [5, 20],
        "max_features": ["sqrt", 0.3],
    },
    "gradient_boosting": {
        "n_estimators": [100, 200],
        "learning_rate": [0.03, 0.05, 0.1],
        "max_depth": [2, 3],
        "min_samples_leaf": [20, 40],
    },
    "adaboost": {
        "n_estimators": [100, 200],
        "learning_rate": [0.05, 0.1, 1.0],
    },
    "mlp": {
        "hidden_layer_sizes": [(16,), (32,), (64,), (32, 16)],
        "alpha": [0.0001, 0.001, 0.01],
        "max_iter": [300],
    },
    "logistic": {"C": [0.1, 0.3, 1.0, 3.0]},
    "gam": {"n_knots": [4, 6], "C": [0.1, 0.3, 1.0]},
}

POSTPROCESS = {
    "cap": [50, 75, 100, None],
    "month_allocation": ["none", "exposure"],
    "flag_quota": [None, 350, 400],
    "seed_average": [1, 3, 5],
}

SEARCH = {
    "population": 24,
    "generations": 12,
    "budget": 300,
    "workers": 6,
    "mutation_rate": 0.30,
    "crossover_rate": 0.70,
    "tournament": 3,
    "seed": 42,
}

# Adoption gate (pre-registered): a challenger must pass this before replacing C1.
GATE = {
    "h243_gain": 6,
    "h500_gain": 6,
    "ap_loss_max": 0.0,
    "paired_ci_positive": True,
}

# Rate-matched 2026 cut: 500 / 72,670 = 243 / 35,281.
H243 = 243
H500 = 500
H161 = 161
