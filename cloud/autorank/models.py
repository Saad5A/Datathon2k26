"""Model factory for AutoRank Lab."""
from __future__ import annotations

import importlib.util

import numpy as np
from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def available_models() -> list[str]:
    models = [
        "hgb",
        "logistic",
        "gam",
        "random_forest",
        "extra_trees",
        "gradient_boosting",
        "adaboost",
        "mlp",
    ]
    if _has("lightgbm"):
        models.append("lightgbm")
    if _has("xgboost"):
        models.append("xgboost")
    if _has("catboost"):
        models.append("catboost")
    return models


def make_model(family: str, params: dict, seed: int = 0):
    if family == "hgb":
        return HistGradientBoostingClassifier(
            max_depth=int(params.get("max_depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_iter=int(params.get("max_iter", 150)),
            min_samples_leaf=int(params.get("min_samples_leaf", 40)),
            l2_regularization=float(params.get("l2_regularization", 5.0)),
            early_stopping=False,
            random_state=seed,
        )
    if family == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            num_leaves=int(params.get("num_leaves", 15)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            n_estimators=int(params.get("n_estimators", 300)),
            min_child_samples=int(params.get("min_child_samples", 40)),
            reg_lambda=float(params.get("reg_lambda", 5.0)),
            n_jobs=1,
            random_state=seed,
            verbosity=-1,
        )
    if family == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            max_depth=int(params.get("max_depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            n_estimators=int(params.get("n_estimators", 300)),
            min_child_weight=float(params.get("min_child_weight", 5)),
            reg_lambda=float(params.get("reg_lambda", 5.0)),
            n_jobs=1,
            random_state=seed,
            eval_metric="logloss",
            tree_method="hist",
        )
    if family == "catboost":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            depth=int(params.get("depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            iterations=int(params.get("iterations", 300)),
            l2_leaf_reg=float(params.get("l2_leaf_reg", 5.0)),
            random_seed=seed,
            thread_count=1,
            verbose=False,
            allow_writing_files=False,
        )
    if family == "random_forest":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(
                n_estimators=int(params.get("n_estimators", 300)),
                max_depth=params.get("max_depth", 10),
                min_samples_leaf=int(params.get("min_samples_leaf", 10)),
                max_features=params.get("max_features", "sqrt"),
                n_jobs=1,
                random_state=seed,
            ),
        )
    if family == "extra_trees":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            ExtraTreesClassifier(
                n_estimators=int(params.get("n_estimators", 300)),
                max_depth=params.get("max_depth", 10),
                min_samples_leaf=int(params.get("min_samples_leaf", 10)),
                max_features=params.get("max_features", "sqrt"),
                n_jobs=1,
                random_state=seed,
            ),
        )
    if family == "gradient_boosting":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            GradientBoostingClassifier(
                n_estimators=int(params.get("n_estimators", 150)),
                learning_rate=float(params.get("learning_rate", 0.05)),
                max_depth=int(params.get("max_depth", 2)),
                min_samples_leaf=int(params.get("min_samples_leaf", 20)),
                random_state=seed,
            ),
        )
    if family == "adaboost":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            AdaBoostClassifier(
                n_estimators=int(params.get("n_estimators", 150)),
                learning_rate=float(params.get("learning_rate", 0.1)),
                random_state=seed,
            ),
        )
    if family == "mlp":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(params.get("hidden_layer_sizes", (32,))),
                alpha=float(params.get("alpha", 0.001)),
                max_iter=int(params.get("max_iter", 300)),
                early_stopping=True,
                n_iter_no_change=10,
                random_state=seed,
            ),
        )
    if family == "logistic":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(
                C=float(params.get("C", 1.0)),
                max_iter=5000,
                class_weight=None,
                random_state=seed,
            ),
        )
    if family == "gam":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            SplineTransformer(
                n_knots=int(params.get("n_knots", 4)),
                degree=3,
                extrapolation="linear",
                include_bias=False,
            ),
            LogisticRegression(
                C=float(params.get("C", 0.3)),
                max_iter=5000,
                class_weight=None,
                random_state=seed,
            ),
        )
    raise ValueError(f"unknown model family: {family}")


def predict_scores(model, X) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(X)
        if p.ndim == 2 and p.shape[1] == 2:
            return p[:, 1]
    if hasattr(model, "decision_function"):
        return model.decision_function(X)
    return np.asarray(model.predict(X), dtype=float)


def fit_predict(
    family: str,
    params: dict,
    Xtr,
    ytr: np.ndarray,
    Xte,
    seed: int = 0,
) -> np.ndarray:
    model = make_model(family, params, seed=seed)
    model.fit(Xtr, np.asarray(ytr, dtype=np.int8))
    return predict_scores(model, Xte)


def complexity(genome: dict) -> float:
    groups = len(genome.get("features", []))
    family = genome.get("model", "hgb")
    base = {
        "hgb": 1.0, "lightgbm": 1.2, "xgboost": 1.3, "catboost": 1.3,
        "logistic": 0.7, "gam": 1.4, "random_forest": 1.6, "extra_trees": 1.6,
        "gradient_boosting": 1.5, "adaboost": 1.4, "mlp": 2.0,
    }.get(family, 1.0)
    params = genome.get("params", {})
    size = 1.0
    for key in ("max_depth", "depth", "num_leaves", "n_estimators", "iterations", "max_iter", "n_knots"):
        if key in params:
            size += float(params[key]) / 500.0
    return round(groups * 0.25 + base + size, 4)
