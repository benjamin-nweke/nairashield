"""
Unit tests for the NairaShield Rules Engine.
"""

from datetime import datetime
from src.rules.engine import RuleEngine

def test_bvn_mismatch():
    engine = RuleEngine()
    tx = {
        "amount": 5000.0,
        "channel": "MOBILEAPP",
        "location": "Lagos",
        "historical_locations": ["Lagos"],
        "device_is_new": False,
        "tx_count_last_hour": 1,
        "bvn_matched": False  # BVN mismatched
    }
    res = engine.evaluate(tx)
    assert "BVN_DETAILS_MISMATCH" in res["triggered_rules"]
    assert res["rule_risk_score"] >= 0.9
    assert res["rule_decision"] == "BLOCKED"

def test_ussd_limit_exceeded():
    engine = RuleEngine()
    tx = {
        "amount": 25000.0,  # Limits is 20,000 NGN
        "channel": "USSD",
        "location": "Lagos",
        "historical_locations": ["Lagos"],
        "device_is_new": False,
        "tx_count_last_hour": 1,
        "bvn_matched": True
    }
    res = engine.evaluate(tx)
    assert "USSD_SINGLE_LIMIT_EXCEEDED" in res["triggered_rules"]
    assert res["rule_decision"] == "BLOCKED"
