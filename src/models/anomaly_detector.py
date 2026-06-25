"""
Machine learning based anomaly detection for NairaShield.
Uses scikit-learn's Isolation Forest to identify fraud patterns
not caught by traditional rule systems (e.g. subtle multi-day behavior changes).
"""

import math
from datetime import datetime

try:
    import numpy as np
    import pandas as pd
    PANDAS_NUMPY_AVAILABLE = True
except ImportError:
    PANDAS_NUMPY_AVAILABLE = False

try:
    if PANDAS_NUMPY_AVAILABLE:
        from sklearn.ensemble import IsolationForest
        SKLEARN_AVAILABLE = True
    else:
        SKLEARN_AVAILABLE = False
except ImportError:
    SKLEARN_AVAILABLE = False


class AnomalyDetector:
    def __init__(self):
        self.model = None
        self.is_trained = False
        # Fallback parameters if sklearn is missing
        self.mean_amount = 50000.0
        self.std_amount = 120000.0

    def preprocess(self, transactions: list):
        """
        Converts list of transaction dicts into numerical feature matrix.
        """
        if not PANDAS_NUMPY_AVAILABLE:
            return None
            
        df = pd.DataFrame(transactions)
        
        # 1. Feature: Numeric Amount
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        
        # 2. Feature: Hour of day
        def get_hour(ts):
            try:
                return datetime.fromisoformat(ts).hour
            except Exception:
                return 12
        df["hour"] = df["timestamp"].apply(get_hour)
        
        # 3. Feature: Channel encoding (USSD=0, Web=1, MobileApp=2, POS=3, ATM=4)
        channel_map = {"USSD": 0, "WEB": 1, "MOBILEAPP": 2, "POS": 3, "ATM": 4}
        df["channel_encoded"] = df["channel"].str.upper().map(channel_map).fillna(2)
        
        # 4. Feature: Location index (Lagos=0, Abuja=1, PortHarcourt=2, Kano=3, Other=4)
        loc_map = {"LAGOS": 0, "ABUJA": 1, "PORT HARCOURT": 2, "KANO": 3}
        df["location_encoded"] = df["location"].str.upper().map(loc_map).fillna(4)
        
        # 5. Feature: Velocity count
        df["tx_count_last_hour"] = pd.to_numeric(df["tx_count_last_hour"], errors="coerce").fillna(0)
        
        return df[["amount", "hour", "channel_encoded", "location_encoded", "tx_count_last_hour"]]

    def train(self, transactions: list):
        """
        Trains the Isolation Forest model on historical (mostly benign) transaction data.
        """
        if not transactions:
            return

        # Keep fallback stats updated
        amounts = [tx.get("amount", 0.0) for tx in transactions]
        
        if PANDAS_NUMPY_AVAILABLE:
            self.mean_amount = np.mean(amounts)
            self.std_amount = np.std(amounts) if np.std(amounts) > 0 else 1.0
        else:
            # Pure Python mean and standard deviation
            self.mean_amount = sum(amounts) / len(amounts)
            variance = sum((x - self.mean_amount) ** 2 for x in amounts) / len(amounts)
            self.std_amount = math.sqrt(variance) if variance > 0 else 1.0

        if not SKLEARN_AVAILABLE or not PANDAS_NUMPY_AVAILABLE:
            self.is_trained = True
            return

        try:
            features_df = self.preprocess(transactions)
            # Isolation Forest anomaly model
            self.model = IsolationForest(
                n_estimators=100,
                contamination=0.03,  # Target 3% synthetic outliers
                random_state=42
            )
            self.model.fit(features_df)
            self.is_trained = True
        except Exception:
            # Silence failures to run gracefully on fallback
            self.is_trained = True

    def predict_anomaly_score(self, transaction: dict) -> float:
        """
        Predicts an anomaly score for a single transaction.
        Returns a value between 0.0 (perfectly normal) and 1.0 (highly anomalous).
        """
        if not self.is_trained:
            return 0.1

        amount = transaction.get("amount", 0.0)
        
        if SKLEARN_AVAILABLE and self.model is not None and PANDAS_NUMPY_AVAILABLE:
            try:
                features_df = self.preprocess([transaction])
                # decision_function returns negative values for anomalies, positive for normal
                score = self.model.decision_function(features_df)[0]
                # Map decision function score to a 0.0 - 1.0 risk scale
                mapped_score = 1.0 - (score + 0.5)
                return float(np.clip(mapped_score, 0.0, 1.0))
            except Exception:
                pass

        # Fallback scoring logic based on statistical outliers
        # If amount is more than 3 standard deviations from average, it is anomalous
        z_score = abs(amount - self.mean_amount) / self.std_amount
        if z_score > 3.0:
            return 0.85
        elif z_score > 2.0:
            return 0.60
        return 0.15

