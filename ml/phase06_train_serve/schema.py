"""Shared paths and feature schema for the v3 click ranker."""

from __future__ import annotations

from pathlib import Path

from ml.phase02_features.encode import NUMERIC_FEATURE_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = REPO_ROOT / "ml" / "artifacts"
ARTIFACT_PATH = ARTIFACTS_DIR / "click_logreg_v3.joblib"
META_PATH = ARTIFACTS_DIR / "click_logreg_v3.meta.json"

FEATURE_NAMES = list(NUMERIC_FEATURE_NAMES)
FEATURE_SCHEMA_VERSION = "fs1"
MODEL_VERSION = "v3"
TOP_K = 5
