"""
NairaShield Model Drift Monitor & Auto-Retraining Engine.

Tracks data drift and model performance weekly using Evidently AI.
Automatically retrains the production XGBoost model when:
  - F1-score drops below the configured threshold (default: 0.85)
  - Evidently detects statistically significant data drift (>30% features drifted)

All monitoring checks and retraining events are logged to a SQLite database.

Usage:
    # Run a single check immediately:
    python drift_monitor.py --check

    # Start weekly automated scheduler (runs check every 7 days):
    python drift_monitor.py --schedule

    # Show recent event history from the database:
    python drift_monitor.py --history [--limit N]

    # Force retrain (bypass threshold checks):
    python drift_monitor.py --retrain
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import logging
import argparse
import threading
import traceback
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import joblib

# =====================================================================
# DEPENDENCY CHECKS
# =====================================================================

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from sklearn.metrics import (
        f1_score, accuracy_score, precision_score,
        recall_score, roc_auc_score
    )
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from imblearn.over_sampling import SMOTE
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False

try:
    from evidently import ColumnMapping
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset, ClassificationPreset
    from evidently.metrics import (
        DatasetDriftMetric,
        DatasetMissingValuesSummaryMetric,
        ColumnDriftMetric,
    )
    EVIDENTLY_AVAILABLE = True
except ImportError:
    EVIDENTLY_AVAILABLE = False

# =====================================================================
# CONFIGURATION
# =====================================================================

CONFIG = {
    # Paths
    "reference_data_path":  "train_smote.csv",
    "current_data_path":    "test.csv",
    "processed_data_path":  "processed_fraud_data.csv",
    "model_path":           "xgboost_model_tuned.joblib",
    "model_backup_dir":     "model_backups",
    "hyperparams_path":     os.path.join("config", "best_hyperparameters.json"),
    "reports_dir":          "drift_reports",
    "db_path":              "drift_monitor.db",

    # Thresholds
    "f1_threshold":         0.85,    # Retrain if F1 drops below this
    "drift_share_threshold":0.30,    # Retrain if >30% features drift
    "psi_threshold":        0.20,    # Population Stability Index warning level

    # Scheduler
    "check_interval_days":  7,       # Weekly check cadence
    "max_backup_count":     10,      # Keep last N model backups

    # Retraining
    "target_column":        "is_fraud",
    "feature_columns": [
        "amount", "channel_CARD_HOST", "channel_CARD_PHONE",
        "channel_CARD_RECURRING", "channel_CARD_STORE", "channel_CARD_WEB",
        "channel_CASH_IN", "channel_CASH_OUT", "channel_DEBIT",
        "channel_PAYMENT", "channel_TRANSFER",
        "source_dataset_IEEE-CIS", "source_dataset_PaySim"
    ],
}

# =====================================================================
# LOGGING
# =====================================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s  %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("drift_monitor.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("NairaShield.DriftMonitor")

# =====================================================================
# SQLITE AUDIT DATABASE
# =====================================================================

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS drift_checks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    check_timestamp     TEXT NOT NULL,
    check_type          TEXT NOT NULL,           -- 'scheduled' | 'manual' | 'forced_retrain'
    reference_dataset   TEXT,
    current_dataset     TEXT,
    -- Performance Metrics
    f1_score            REAL,
    accuracy            REAL,
    precision_score     REAL,
    recall_score        REAL,
    auc_roc             REAL,
    f1_threshold        REAL,
    f1_passed           INTEGER,                 -- 1 = PASS, 0 = FAIL
    -- Drift Metrics
    evidently_available INTEGER,                 -- 1 = yes, 0 = no
    drift_detected      INTEGER,                 -- 1 = yes, 0 = no
    drift_share         REAL,                    -- fraction of drifted features
    drifted_features    TEXT,                    -- JSON list of feature names
    drift_threshold     REAL,
    -- Decision
    retrain_triggered   INTEGER,                 -- 1 = yes, 0 = no
    retrain_reason      TEXT,
    -- Report
    report_path         TEXT
);

CREATE TABLE IF NOT EXISTS retrain_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_timestamp     TEXT NOT NULL,
    trigger_check_id    INTEGER,                 -- FK -> drift_checks.id
    trigger_reason      TEXT NOT NULL,
    -- Training Data
    training_data_path  TEXT,
    training_rows       INTEGER,
    fraud_rows          INTEGER,
    legit_rows          INTEGER,
    smote_applied       INTEGER,
    -- Model Before
    model_path          TEXT,
    backup_path         TEXT,
    f1_before           REAL,
    -- Model After
    f1_after            REAL,
    accuracy_after      REAL,
    precision_after     REAL,
    recall_after        REAL,
    auc_roc_after       REAL,
    -- Outcome
    success             INTEGER,                 -- 1 = success, 0 = failed
    error_message       TEXT,
    duration_seconds    REAL,
    FOREIGN KEY (trigger_check_id) REFERENCES drift_checks(id)
);

CREATE TABLE IF NOT EXISTS scheduler_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    log_timestamp       TEXT NOT NULL,
    event_type          TEXT NOT NULL,           -- 'started' | 'check_completed' | 'error' | 'stopped'
    message             TEXT,
    next_check_time     TEXT
);
"""


class DriftDatabase:
    """SQLite-backed audit log for all drift monitoring and retraining events."""

    def __init__(self, db_path: str = CONFIG["db_path"]):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(DB_SCHEMA)
        log.info(f"[DB] SQLite audit database initialised: {self.db_path}")

    def log_drift_check(self, data: dict) -> int:
        """Insert a drift check record and return its row ID."""
        sql = """
        INSERT INTO drift_checks (
            check_timestamp, check_type, reference_dataset, current_dataset,
            f1_score, accuracy, precision_score, recall_score, auc_roc,
            f1_threshold, f1_passed,
            evidently_available, drift_detected, drift_share, drifted_features,
            drift_threshold, retrain_triggered, retrain_reason, report_path
        ) VALUES (
            :check_timestamp, :check_type, :reference_dataset, :current_dataset,
            :f1_score, :accuracy, :precision_score, :recall_score, :auc_roc,
            :f1_threshold, :f1_passed,
            :evidently_available, :drift_detected, :drift_share, :drifted_features,
            :drift_threshold, :retrain_triggered, :retrain_reason, :report_path
        )
        """
        with self._connect() as conn:
            cur = conn.execute(sql, data)
            return cur.lastrowid

    def log_retrain_event(self, data: dict) -> int:
        """Insert a retraining event record and return its row ID."""
        sql = """
        INSERT INTO retrain_events (
            event_timestamp, trigger_check_id, trigger_reason,
            training_data_path, training_rows, fraud_rows, legit_rows, smote_applied,
            model_path, backup_path, f1_before,
            f1_after, accuracy_after, precision_after, recall_after, auc_roc_after,
            success, error_message, duration_seconds
        ) VALUES (
            :event_timestamp, :trigger_check_id, :trigger_reason,
            :training_data_path, :training_rows, :fraud_rows, :legit_rows, :smote_applied,
            :model_path, :backup_path, :f1_before,
            :f1_after, :accuracy_after, :precision_after, :recall_after, :auc_roc_after,
            :success, :error_message, :duration_seconds
        )
        """
        with self._connect() as conn:
            cur = conn.execute(sql, data)
            return cur.lastrowid

    def log_scheduler(self, event_type: str, message: str = "", next_check_time: str = ""):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO scheduler_log (log_timestamp, event_type, message, next_check_time) "
                "VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), event_type, message, next_check_time)
            )

    def get_recent_checks(self, limit: int = 20) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM drift_checks ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_retrains(self, limit: int = 20) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM retrain_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_last_f1(self) -> Optional[float]:
        """Return the most recent F1-score from the drift_checks table."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT f1_score FROM drift_checks ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return float(row["f1_score"]) if row and row["f1_score"] is not None else None


# =====================================================================
# PERFORMANCE EVALUATOR
# =====================================================================

def evaluate_model_performance(
    model_path: str,
    test_data_path: str,
    feature_cols: list,
    target_col: str
) -> dict:
    """
    Load the model and evaluate it against the current test dataset.
    Returns a dict of metrics: f1, accuracy, precision, recall, auc_roc.
    """
    if not SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn is required for model evaluation.")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not os.path.exists(test_data_path):
        raise FileNotFoundError(f"Test data not found: {test_data_path}")

    log.info(f"[Eval] Loading model: {model_path}")
    model = joblib.load(model_path)

    log.info(f"[Eval] Loading test data: {test_data_path}")
    df = pd.read_csv(test_data_path)

    # Ensure all feature columns are present
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        log.warning(f"[Eval] Missing feature columns: {missing} — filling with 0.0")
        for c in missing:
            df[c] = 0.0

    X = df[feature_cols]
    y = df[target_col]

    preds = model.predict(X)
    probs = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else preds.astype(float)

    metrics = {
        "f1_score":       round(float(f1_score(y, preds, zero_division=0)), 6),
        "accuracy":       round(float(accuracy_score(y, preds)), 6),
        "precision":      round(float(precision_score(y, preds, zero_division=0)), 6),
        "recall":         round(float(recall_score(y, preds, zero_division=0)), 6),
        "auc_roc":        round(float(roc_auc_score(y, probs)), 6),
        "support_total":  int(len(y)),
        "support_fraud":  int(y.sum()),
    }
    log.info(
        f"[Eval] F1={metrics['f1_score']:.4f} | "
        f"Acc={metrics['accuracy']:.4f} | "
        f"AUC={metrics['auc_roc']:.4f} | "
        f"Fraud support={metrics['support_fraud']}/{metrics['support_total']}"
    )
    return metrics


# =====================================================================
# EVIDENTLY DRIFT DETECTOR
# =====================================================================

def run_evidently_drift(
    reference_path: str,
    current_path: str,
    feature_cols: list,
    target_col: str,
    reports_dir: str,
    check_id: str = ""
) -> dict:
    """
    Runs Evidently AI data drift and classification performance reports.
    Returns a summary dict:
        drift_detected, drift_share, drifted_features, report_path, evidently_available
    """
    result = {
        "evidently_available": EVIDENTLY_AVAILABLE,
        "drift_detected":      False,
        "drift_share":         0.0,
        "drifted_features":    [],
        "report_path":         None,
    }

    if not EVIDENTLY_AVAILABLE:
        log.warning("[Evidently] Package not installed. Running statistical fallback drift detection.")
        result.update(_fallback_drift_detection(reference_path, current_path, feature_cols))
        return result

    try:
        log.info("[Evidently] Loading reference and current datasets...")
        ref_df = pd.read_csv(reference_path)
        cur_df = pd.read_csv(current_path)

        # Align columns — only use feature + target columns
        all_cols = feature_cols + [target_col]
        ref_df = ref_df[[c for c in all_cols if c in ref_df.columns]].copy()
        cur_df = cur_df[[c for c in all_cols if c in cur_df.columns]].copy()

        # Add model predictions to current data for ClassificationPreset
        model_path = CONFIG["model_path"]
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            cur_pred = model.predict(cur_df[feature_cols])
            cur_df["prediction"] = cur_pred
            ref_pred = model.predict(ref_df[feature_cols])
            ref_df["prediction"] = ref_pred

        column_mapping = ColumnMapping(
            target=target_col,
            prediction="prediction" if "prediction" in cur_df.columns else None,
            numerical_features=feature_cols,
        )

        # Build Evidently Report
        report = Report(metrics=[
            DataDriftPreset(),
            DatasetDriftMetric(),
            DatasetMissingValuesSummaryMetric(),
        ])
        report.run(
            reference_data=ref_df,
            current_data=cur_df,
            column_mapping=column_mapping
        )

        # Extract drift summary
        report_dict = report.as_dict()
        metrics_results = report_dict.get("metrics", [])

        drift_share = 0.0
        drifted_features = []

        for metric in metrics_results:
            metric_id = metric.get("metric", "")
            metric_result = metric.get("result", {})

            if "DatasetDriftMetric" in metric_id:
                drift_share = float(metric_result.get("share_of_drifted_columns", 0.0))
                drifted_features = [
                    col for col, details in metric_result.get("drift_by_columns", {}).items()
                    if details.get("drift_detected", False) and col in feature_cols
                ]

        drift_detected = drift_share >= CONFIG["drift_share_threshold"]

        log.info(
            f"[Evidently] Drift share: {drift_share:.2%} | "
            f"Drifted features: {len(drifted_features)} | "
            f"Drift detected: {drift_detected}"
        )

        # Save HTML report
        os.makedirs(reports_dir, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"drift_report_{ts_str}_{check_id}.html"
        report_path = os.path.join(reports_dir, report_filename)
        report.save_html(report_path)
        log.info(f"[Evidently] Report saved: {report_path}")

        result.update({
            "drift_detected":   drift_detected,
            "drift_share":      round(drift_share, 6),
            "drifted_features": drifted_features,
            "report_path":      report_path,
        })

    except Exception as e:
        log.error(f"[Evidently] Report generation failed: {e}\n{traceback.format_exc()}")
        # Fall back to statistical test
        result.update(_fallback_drift_detection(reference_path, current_path, feature_cols))

    return result


def _fallback_drift_detection(
    reference_path: str,
    current_path: str,
    feature_cols: list
) -> dict:
    """
    Statistical fallback when Evidently is unavailable.
    Uses Population Stability Index (PSI) per feature.
    PSI > 0.20 indicates significant drift.
    """
    log.info("[Fallback] Running PSI-based drift detection...")

    try:
        ref_df = pd.read_csv(reference_path)
        cur_df = pd.read_csv(current_path)

        drifted = []
        psi_scores = {}

        for col in feature_cols:
            if col not in ref_df.columns or col not in cur_df.columns:
                continue
            psi = _compute_psi(ref_df[col].values, cur_df[col].values, bins=10)
            psi_scores[col] = psi
            if psi > CONFIG["psi_threshold"]:
                drifted.append(col)
                log.info(f"[PSI] {col}: PSI={psi:.4f} -> DRIFTED")

        drift_share = len(drifted) / max(len(feature_cols), 1)
        drift_detected = drift_share >= CONFIG["drift_share_threshold"]

        log.info(
            f"[Fallback] PSI drift: {len(drifted)}/{len(feature_cols)} features | "
            f"Share={drift_share:.2%} | Detected={drift_detected}"
        )
        return {
            "evidently_available": False,
            "drift_detected":      drift_detected,
            "drift_share":         round(drift_share, 6),
            "drifted_features":    drifted,
            "report_path":         None,
        }
    except Exception as e:
        log.error(f"[Fallback] PSI drift detection failed: {e}")
        return {
            "evidently_available": False,
            "drift_detected":      False,
            "drift_share":         0.0,
            "drifted_features":    [],
            "report_path":         None,
        }


def _compute_psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Compute Population Stability Index between two distributions."""
    min_val = min(reference.min(), current.min())
    max_val = max(reference.max(), current.max())
    if max_val == min_val:
        return 0.0

    breakpoints = np.linspace(min_val, max_val, bins + 1)
    ref_counts = np.histogram(reference, bins=breakpoints)[0]
    cur_counts = np.histogram(current, bins=breakpoints)[0]

    # Replace zeros with small epsilon to avoid log(0)
    eps = 1e-6
    ref_pct = (ref_counts + eps) / (len(reference) + eps * bins)
    cur_pct = (cur_counts + eps) / (len(current) + eps * bins)

    psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return float(psi)


# =====================================================================
# AUTO-RETRAINER
# =====================================================================

def retrain_model(
    trigger_reason: str,
    trigger_check_id: Optional[int],
    db: "DriftDatabase",
    f1_before: Optional[float] = None,
) -> bool:
    """
    Retrains the XGBoost (Tuned) model on the latest available data,
    backs up the old model, and replaces the production artifact.
    All outcomes are logged to the SQLite database.

    Returns True on success, False on failure.
    """
    if not (XGB_AVAILABLE and SKLEARN_AVAILABLE):
        log.error("[Retrain] XGBoost or scikit-learn not available. Cannot retrain.")
        return False

    start_time = time.perf_counter()
    ts = datetime.now().isoformat()
    log.info(f"[Retrain] ============ Starting retraining ============")
    log.info(f"[Retrain] Trigger: {trigger_reason}")

    event = {
        "event_timestamp":   ts,
        "trigger_check_id":  trigger_check_id,
        "trigger_reason":    trigger_reason,
        "training_data_path": None,
        "training_rows":     0,
        "fraud_rows":        0,
        "legit_rows":        0,
        "smote_applied":     0,
        "model_path":        CONFIG["model_path"],
        "backup_path":       None,
        "f1_before":         f1_before,
        "f1_after":          None,
        "accuracy_after":    None,
        "precision_after":   None,
        "recall_after":      None,
        "auc_roc_after":     None,
        "success":           0,
        "error_message":     None,
        "duration_seconds":  0.0,
    }

    try:
        # ---- Step 1: Decide which training data to use ----
        # Prefer the latest processed_fraud_data.csv (full dataset),
        # fallback to train_smote.csv
        training_path = CONFIG["processed_data_path"]
        if not os.path.exists(training_path):
            training_path = CONFIG["reference_data_path"]  # train_smote.csv
        if not os.path.exists(training_path):
            raise FileNotFoundError("No training data found. Expected processed_fraud_data.csv or train_smote.csv")

        event["training_data_path"] = training_path
        log.info(f"[Retrain] Training data: {training_path}")

        df = pd.read_csv(training_path)
        target_col = CONFIG["target_column"]
        feature_cols = CONFIG["feature_columns"]

        # Drop any columns not in the expected set
        available_features = [c for c in feature_cols if c in df.columns]
        if not available_features:
            raise ValueError(f"None of the expected features found in {training_path}")

        # Drop transaction_id if present
        if "transaction_id" in df.columns:
            df = df.drop(columns=["transaction_id"])

        X = df[available_features]
        y = df[target_col]

        fraud_count = int(y.sum())
        legit_count = int((y == 0).sum())
        event["training_rows"] = len(df)
        event["fraud_rows"]    = fraud_count
        event["legit_rows"]    = legit_count

        log.info(f"[Retrain] Dataset: {len(df)} rows | Fraud={fraud_count} | Legit={legit_count}")

        # ---- Step 2: Train/test split ----
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y
        )

        # ---- Step 3: SMOTE ----
        if IMBLEARN_AVAILABLE and fraud_count >= 2:
            k = min(2, fraud_count - 1, int(y_train.sum()) - 1)
            if k >= 1:
                smote = SMOTE(random_state=42, k_neighbors=k)
                X_train, y_train = smote.fit_resample(X_train, y_train)
                event["smote_applied"] = 1
                log.info(f"[Retrain] SMOTE applied -> {len(X_train)} training samples")
            else:
                log.warning("[Retrain] Insufficient minority samples for SMOTE. Skipping.")
        else:
            log.info("[Retrain] SMOTE skipped (imblearn unavailable or insufficient fraud samples)")

        # ---- Step 4: Load hyperparameters ----
        xgb_params = {
            "use_label_encoder": False,
            "eval_metric": "logloss",
            "random_state": 42,
            "n_estimators": 267,
            "max_depth": 9,
            "learning_rate": 0.138,
            "subsample": 0.747,
            "colsample_bytree": 0.761,
            "min_child_weight": 10,
            "scale_pos_weight": max(1.0, legit_count / max(fraud_count, 1)),
            "n_jobs": -1,
        }
        if os.path.exists(CONFIG["hyperparams_path"]):
            try:
                with open(CONFIG["hyperparams_path"], "r") as f:
                    saved = json.load(f).get("xgboost", {})
                xgb_params.update(saved)
                xgb_params["use_label_encoder"] = False
                xgb_params["eval_metric"] = "logloss"
                xgb_params["random_state"] = 42
                log.info("[Retrain] Loaded hyperparameters from config/best_hyperparameters.json")
            except Exception as hp_err:
                log.warning(f"[Retrain] Could not load hyperparameters: {hp_err}. Using defaults.")

        # ---- Step 5: Train ----
        log.info("[Retrain] Training XGBoost (Tuned)...")
        new_model = xgb.XGBClassifier(**xgb_params)
        new_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

        # ---- Step 6: Evaluate new model ----
        preds = new_model.predict(X_test)
        probs = new_model.predict_proba(X_test)[:, 1]

        new_f1       = round(float(f1_score(y_test, preds, zero_division=0)), 6)
        new_acc      = round(float(accuracy_score(y_test, preds)), 6)
        new_prec     = round(float(precision_score(y_test, preds, zero_division=0)), 6)
        new_recall   = round(float(recall_score(y_test, preds, zero_division=0)), 6)
        new_auc      = round(float(roc_auc_score(y_test, probs)), 6)

        event["f1_after"]        = new_f1
        event["accuracy_after"]  = new_acc
        event["precision_after"] = new_prec
        event["recall_after"]    = new_recall
        event["auc_roc_after"]   = new_auc

        log.info(
            f"[Retrain] New model metrics: "
            f"F1={new_f1:.4f} | Acc={new_acc:.4f} | AUC={new_auc:.4f}"
        )

        # ---- Step 7: Backup old model ----
        os.makedirs(CONFIG["model_backup_dir"], exist_ok=True)
        backup_path = None
        if os.path.exists(CONFIG["model_path"]):
            ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"xgboost_model_tuned_backup_{ts_tag}.joblib"
            backup_path = os.path.join(CONFIG["model_backup_dir"], backup_filename)
            shutil.copy2(CONFIG["model_path"], backup_path)
            event["backup_path"] = backup_path
            log.info(f"[Retrain] Old model backed up: {backup_path}")

            # Prune old backups beyond max_backup_count
            _prune_old_backups(CONFIG["model_backup_dir"])

        # ---- Step 8: Save new model as production ----
        joblib.dump(new_model, CONFIG["model_path"])
        log.info(f"[Retrain] New model saved: {CONFIG['model_path']}")

        duration = round(time.perf_counter() - start_time, 3)
        event["success"]          = 1
        event["duration_seconds"] = duration

        retrain_id = db.log_retrain_event(event)
        log.info(
            f"[Retrain] ============ Retraining COMPLETE ============\n"
            f"          Duration:   {duration:.2f}s\n"
            f"          F1 Before:  {f1_before or 'N/A'}\n"
            f"          F1 After:   {new_f1:.4f}\n"
            f"          DB Event:   retrain_events.id={retrain_id}"
        )
        return True

    except Exception as e:
        duration = round(time.perf_counter() - start_time, 3)
        event["error_message"]    = str(e)
        event["duration_seconds"] = duration
        event["success"]          = 0
        db.log_retrain_event(event)
        log.error(f"[Retrain] FAILED after {duration:.2f}s: {e}\n{traceback.format_exc()}")
        return False


def _prune_old_backups(backup_dir: str):
    """Remove the oldest model backups beyond the max_backup_count limit."""
    backups = sorted([
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.endswith(".joblib")
    ])
    excess = len(backups) - CONFIG["max_backup_count"]
    for old_file in backups[:excess]:
        try:
            os.remove(old_file)
            log.info(f"[Retrain] Pruned old backup: {old_file}")
        except Exception:
            pass


# =====================================================================
# MAIN MONITORING CHECK
# =====================================================================

def run_drift_check(
    check_type: str = "scheduled",
    db: Optional["DriftDatabase"] = None,
    force_retrain: bool = False,
) -> dict:
    """
    Execute a complete drift monitoring cycle:
      1. Evaluate current model F1 on the latest test data
      2. Run Evidently drift analysis on reference vs current data
      3. Decide whether to retrain (F1 below threshold OR drift detected)
      4. Retrain if needed
      5. Log everything to SQLite

    Returns the check result dict.
    """
    if db is None:
        db = DriftDatabase()

    ts = datetime.now().isoformat()
    log.info(f"\n{'='*60}")
    log.info(f"[Check] NairaShield Drift Monitor - {check_type.upper()} CHECK")
    log.info(f"[Check] Timestamp: {ts}")
    log.info(f"{'='*60}")

    check_record = {
        "check_timestamp":    ts,
        "check_type":         check_type,
        "reference_dataset":  CONFIG["reference_data_path"],
        "current_dataset":    CONFIG["current_data_path"],
        "f1_score":           None,
        "accuracy":           None,
        "precision_score":    None,
        "recall_score":       None,
        "auc_roc":            None,
        "f1_threshold":       CONFIG["f1_threshold"],
        "f1_passed":          None,
        "evidently_available":int(EVIDENTLY_AVAILABLE),
        "drift_detected":     0,
        "drift_share":        0.0,
        "drifted_features":   "[]",
        "drift_threshold":    CONFIG["drift_share_threshold"],
        "retrain_triggered":  0,
        "retrain_reason":     "",
        "report_path":        None,
    }

    retrain_reasons = []
    f1_val = None

    # ---- STEP 1: Performance Evaluation ----
    try:
        log.info("[Check] Step 1/3: Evaluating model performance...")
        perf = evaluate_model_performance(
            model_path=CONFIG["model_path"],
            test_data_path=CONFIG["current_data_path"],
            feature_cols=CONFIG["feature_columns"],
            target_col=CONFIG["target_column"],
        )
        f1_val = perf["f1_score"]
        check_record.update({
            "f1_score":      f1_val,
            "accuracy":      perf["accuracy"],
            "precision_score": perf["precision"],
            "recall_score":  perf["recall"],
            "auc_roc":       perf["auc_roc"],
            "f1_passed":     int(f1_val >= CONFIG["f1_threshold"]),
        })

        if f1_val < CONFIG["f1_threshold"]:
            reason = f"F1-score ({f1_val:.4f}) below threshold ({CONFIG['f1_threshold']})"
            retrain_reasons.append(reason)
            log.warning(f"[Check] {reason}")
        else:
            log.info(f"[Check] F1={f1_val:.4f} >= threshold {CONFIG['f1_threshold']} -> PASS")

    except FileNotFoundError as e:
        log.warning(f"[Check] Model or data not found for evaluation: {e}")
    except Exception as e:
        log.error(f"[Check] Performance evaluation failed: {e}")

    # ---- STEP 2: Drift Detection ----
    try:
        log.info("[Check] Step 2/3: Running Evidently drift analysis...")
        check_id_tag = ts[:16].replace(":", "").replace("-", "")
        drift_result = run_evidently_drift(
            reference_path=CONFIG["reference_data_path"],
            current_path=CONFIG["current_data_path"],
            feature_cols=CONFIG["feature_columns"],
            target_col=CONFIG["target_column"],
            reports_dir=CONFIG["reports_dir"],
            check_id=check_id_tag,
        )
        check_record.update({
            "evidently_available": int(drift_result["evidently_available"]),
            "drift_detected":      int(drift_result["drift_detected"]),
            "drift_share":         drift_result["drift_share"],
            "drifted_features":    json.dumps(drift_result["drifted_features"]),
            "report_path":         drift_result["report_path"],
        })

        if drift_result["drift_detected"]:
            reason = (
                f"Data drift detected: {drift_result['drift_share']:.1%} of features drifted "
                f"(threshold={CONFIG['drift_share_threshold']:.0%}). "
                f"Drifted: {drift_result['drifted_features']}"
            )
            retrain_reasons.append(reason)
            log.warning(f"[Check] {reason}")
        else:
            log.info(
                f"[Check] No significant drift detected "
                f"({drift_result['drift_share']:.1%} < {CONFIG['drift_share_threshold']:.0%})"
            )

    except Exception as e:
        log.error(f"[Check] Drift detection error: {e}\n{traceback.format_exc()}")

    # ---- STEP 3: Retrain Decision ----
    should_retrain = bool(retrain_reasons) or force_retrain

    if force_retrain and not retrain_reasons:
        retrain_reasons.append("Manual force retrain requested by operator")

    if should_retrain:
        combined_reason = " | ".join(retrain_reasons)
        log.warning(f"[Check] RETRAIN TRIGGERED: {combined_reason}")
        check_record["retrain_triggered"] = 1
        check_record["retrain_reason"] = combined_reason

        # Persist check record first so retrain can reference its ID
        check_id = db.log_drift_check(check_record)

        log.info("[Check] Step 3/3: Starting automatic retraining...")
        success = retrain_model(
            trigger_reason=combined_reason,
            trigger_check_id=check_id,
            db=db,
            f1_before=f1_val,
        )

        status_word = "SUCCESS" if success else "FAILED"
        log.info(f"[Check] Retraining {status_word}.")
    else:
        log.info("[Check] Step 3/3: No retraining needed. All checks passed.")
        check_record["retrain_reason"] = "No drift or performance degradation detected"
        check_id = db.log_drift_check(check_record)

    summary = {
        "check_id":         check_id,
        "timestamp":        ts,
        "f1_score":         f1_val,
        "f1_passed":        (f1_val or 0.0) >= CONFIG["f1_threshold"],
        "drift_detected":   bool(check_record["drift_detected"]),
        "drift_share":      check_record["drift_share"],
        "retrain_triggered":bool(check_record["retrain_triggered"]),
        "retrain_reason":   check_record["retrain_reason"],
        "report_path":      check_record["report_path"],
    }

    log.info(
        f"\n[Check] SUMMARY\n"
        f"  Check ID      : {check_id}\n"
        f"  F1 Score      : {f1_val or 'N/A'} ({'PASS' if summary['f1_passed'] else 'FAIL'})\n"
        f"  Drift Detected: {summary['drift_detected']}\n"
        f"  Retrained     : {summary['retrain_triggered']}\n"
        f"  Report        : {summary['report_path'] or 'N/A'}"
    )
    return summary


# =====================================================================
# WEEKLY SCHEDULER
# =====================================================================

class DriftScheduler:
    """
    Background scheduler that runs the drift check on a configurable interval.
    Runs in a daemon thread so it does not block the main process.
    """

    def __init__(self, interval_days: float = CONFIG["check_interval_days"]):
        self.interval_seconds = interval_days * 86400
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.db = DriftDatabase()

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="DriftScheduler")
        self._thread.start()
        log.info(
            f"[Scheduler] Started. Check interval: every {CONFIG['check_interval_days']} days. "
            f"Next check in ~{CONFIG['check_interval_days']}d."
        )
        self.db.log_scheduler("started", f"Interval={CONFIG['check_interval_days']}d")

    def stop(self):
        self.running = False
        log.info("[Scheduler] Shutdown requested.")
        self.db.log_scheduler("stopped", "User requested stop")

    def _loop(self):
        while self.running:
            next_check = datetime.now() + timedelta(seconds=self.interval_seconds)
            next_str = next_check.strftime("%Y-%m-%d %H:%M:%S")
            log.info(f"[Scheduler] Sleeping until next check: {next_str}")
            self.db.log_scheduler("check_completed", "Waiting for next interval", next_str)

            # Sleep in short segments to allow clean shutdown
            elapsed = 0.0
            while elapsed < self.interval_seconds and self.running:
                time.sleep(min(60.0, self.interval_seconds - elapsed))
                elapsed += 60.0

            if self.running:
                log.info("[Scheduler] Waking up for scheduled drift check...")
                try:
                    result = run_drift_check(check_type="scheduled", db=self.db)
                    msg = (
                        f"Check complete: F1={result.get('f1_score')}, "
                        f"Drift={result.get('drift_detected')}, "
                        f"Retrained={result.get('retrain_triggered')}"
                    )
                    self.db.log_scheduler("check_completed", msg)
                except Exception as e:
                    self.db.log_scheduler("error", str(e))
                    log.error(f"[Scheduler] Check failed: {e}")


# =====================================================================
# HISTORY DISPLAY
# =====================================================================

def print_history(db: DriftDatabase, limit: int = 10):
    """Print recent drift check and retrain history to stdout."""
    print("\n" + "=" * 70)
    print(f" NairaShield Drift Monitor - Event History (last {limit} checks)")
    print("=" * 70)

    checks = db.get_recent_checks(limit=limit)
    if not checks:
        print("  No drift check records found.")
    else:
        header = f"{'ID':<5} {'Timestamp':<20} {'F1':>6} {'Drift':>6} {'Retrain':>8} {'Reason'}"
        print(f"\n  DRIFT CHECKS:\n  {header}")
        print("  " + "-" * 70)
        for c in checks:
            f1_str   = f"{c['f1_score']:.4f}" if c["f1_score"] is not None else "N/A"
            drift    = "YES" if c["drift_detected"] else "NO"
            retrain  = "YES" if c["retrain_triggered"] else "NO"
            reason   = (c["retrain_reason"] or "")[:45]
            ts       = (c["check_timestamp"] or "")[:19]
            print(f"  {c['id']:<5} {ts:<20} {f1_str:>6} {drift:>6} {retrain:>8}  {reason}")

    retrains = db.get_recent_retrains(limit=limit)
    if retrains:
        print(f"\n  RETRAIN EVENTS:")
        header = f"{'ID':<5} {'Timestamp':<20} {'F1 Before':>9} {'F1 After':>9} {'Success':>8} {'Duration':>9}"
        print(f"  {header}")
        print("  " + "-" * 70)
        for r in retrains:
            f1b  = f"{r['f1_before']:.4f}" if r["f1_before"] is not None else "N/A"
            f1a  = f"{r['f1_after']:.4f}"  if r["f1_after"]  is not None else "N/A"
            ok   = "OK" if r["success"] else "FAILED"
            dur  = f"{r['duration_seconds']:.2f}s"
            ts   = (r["event_timestamp"] or "")[:19]
            print(f"  {r['id']:<5} {ts:<20} {f1b:>9} {f1a:>9} {ok:>8} {dur:>9}")

    print()


# =====================================================================
# CLI ENTRY POINT
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="NairaShield Model Drift Monitor & Auto-Retraining Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python drift_monitor.py --check              Run a single drift check now
  python drift_monitor.py --schedule           Start weekly automated monitoring
  python drift_monitor.py --retrain            Force immediate retraining
  python drift_monitor.py --history --limit 5  Show last 5 check records
  python drift_monitor.py --check --f1 0.90    Override F1 threshold to 0.90
        """
    )
    parser.add_argument("--check",    action="store_true", help="Run a single drift check immediately")
    parser.add_argument("--schedule", action="store_true", help="Start weekly automated drift monitoring scheduler")
    parser.add_argument("--retrain",  action="store_true", help="Force an immediate model retrain regardless of thresholds")
    parser.add_argument("--history",  action="store_true", help="Display recent monitoring history from SQLite database")
    parser.add_argument("--limit",    type=int, default=10, help="Number of history records to display (default: 10)")
    parser.add_argument("--f1",       type=float, help="Override F1-score threshold (e.g. 0.90)")
    parser.add_argument("--drift",    type=float, help="Override drift share threshold (e.g. 0.25)")
    parser.add_argument("--interval", type=float, help="Scheduler interval in days (default: 7)")
    args = parser.parse_args()

    # Apply CLI overrides
    if args.f1:
        CONFIG["f1_threshold"] = args.f1
        log.info(f"[Config] F1 threshold overridden: {args.f1}")
    if args.drift:
        CONFIG["drift_share_threshold"] = args.drift
        log.info(f"[Config] Drift share threshold overridden: {args.drift}")
    if args.interval:
        CONFIG["check_interval_days"] = args.interval
        log.info(f"[Config] Check interval overridden: {args.interval} days")

    db = DriftDatabase()

    if args.history:
        print_history(db, limit=args.limit)
        return

    if args.retrain:
        log.info("[CLI] Force retraining requested.")
        f1_before = db.get_last_f1()
        run_drift_check(check_type="forced_retrain", db=db, force_retrain=True)
        return

    if args.check:
        run_drift_check(check_type="manual", db=db)
        return

    if args.schedule:
        scheduler = DriftScheduler(interval_days=CONFIG["check_interval_days"])
        log.info("[Scheduler] Running initial check on startup...")
        run_drift_check(check_type="scheduled", db=db)
        scheduler.start()
        log.info("[Scheduler] Press Ctrl+C to stop the monitor.")
        try:
            while True:
                time.sleep(30)
        except KeyboardInterrupt:
            scheduler.stop()
            log.info("[Scheduler] Drift monitor stopped.")
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
