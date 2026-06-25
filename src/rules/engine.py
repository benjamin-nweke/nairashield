"""
Rules engine for NairaShield AI.
Applies regulatory and security rules specific to Nigerian financial systems.
"""

from datetime import datetime
from config.settings import (
    MAX_USSD_SINGLE_LIMIT_WITHOUT_TOKEN,
    MAX_USSD_DAILY_LIMIT,
    NIGHT_WINDOW_START,
    NIGHT_WINDOW_END,
    WEIGHTS
)

class RuleEngine:
    def __init__(self):
        self.weights = WEIGHTS

    def evaluate(self, transaction: dict) -> dict:
        """
        Evaluates a transaction dictionary against rule-based criteria.
        Returns a dictionary containing risk score, triggered rules, and pass/fail status.
        """
        triggered_rules = []
        rule_score = 0.0

        amount = transaction.get("amount", 0.0)
        channel = transaction.get("channel", "MobileApp").upper()
        location = transaction.get("location", "Lagos")
        historical_locations = transaction.get("historical_locations", ["Lagos"])
        device_is_new = transaction.get("device_is_new", False)
        tx_count_last_hour = transaction.get("tx_count_last_hour", 0)
        bvn_matched = transaction.get("bvn_matched", True)
        
        # Parse timestamp
        timestamp_str = transaction.get("timestamp", datetime.now().isoformat())
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except Exception:
            timestamp = datetime.now()

        # Rule 1: BVN verification check
        if not bvn_matched:
            triggered_rules.append("BVN_DETAILS_MISMATCH")
            rule_score = max(rule_score, self.weights["bvn_mismatch"])

        # Rule 2: USSD Transfer Checks
        if channel == "USSD":
            if amount > MAX_USSD_SINGLE_LIMIT_WITHOUT_TOKEN:
                triggered_rules.append("USSD_SINGLE_LIMIT_EXCEEDED")
                rule_score = max(rule_score, self.weights["ussd_limit_exceeded"])

        # Rule 3: Night Large Transaction Rule
        # Late night transfers over 500,000 NGN are flagged as suspicious in Nigeria (classic SIM swap drain times)
        hour = timestamp.hour
        if (hour >= NIGHT_WINDOW_START or hour < NIGHT_WINDOW_END) and amount >= 500000.0:
            triggered_rules.append("NIGHT_WINDOW_LARGE_TRANSFER")
            rule_score = max(rule_score, self.weights["night_large_tx"])

        # Rule 4: Velocity Rule (Transaction spamming)
        if tx_count_last_hour >= 5:
            triggered_rules.append("HIGH_TRANSACTION_VELOCITY")
            rule_score = max(rule_score, self.weights["high_velocity"])

        # Rule 5: Location Anomaly (e.g. transacting from London when historical is Lagos/Abuja)
        if location not in historical_locations:
            triggered_rules.append("LOCATION_ANOMALY")
            rule_score = max(rule_score, self.weights["location_anomaly"])

        # Rule 6: New Device Registration first transaction
        if device_is_new and amount >= 100000.0:
            triggered_rules.append("NEW_DEVICE_HIGH_VALUE_TX")
            rule_score = max(rule_score, self.weights["new_device_first_tx"])

        # Status decision based on rule score
        status = "APPROVED"
        if rule_score >= 0.8:
            status = "BLOCKED"
        elif rule_score >= 0.5:
            status = "PENDING_OTP"  # Requires hardware token / second factor validation

        return {
            "rule_risk_score": round(rule_score, 2),
            "triggered_rules": triggered_rules,
            "rule_decision": status
        }
