import sys
import os

# Align python path to workspace root
sys.path.insert(0, os.path.abspath("."))

from src.utils.nuban import validate_nuban, validate_bvn, hash_bvn
from src.rules.engine import RuleEngine

print("=========================================")
print("Executing NairaShield Core Logic Tests...")
print("=========================================")

# 1. NUBAN and BVN tests
try:
    assert validate_nuban("0110000001", "058") is True
    assert validate_nuban("0110000002", "058") is False
    assert validate_nuban("011000000a", "058") is False
    assert validate_nuban("011000000", "058") is False
    print("[OK] NUBAN Check Digit Calculations Validated.")
except AssertionError:
    print("[FAIL] NUBAN calculation checks failed!")
    sys.exit(1)

try:
    assert validate_bvn("12345678901") is True
    assert validate_bvn("12345") is False
    assert validate_bvn("abcdefghijk") is False
    print("[OK] BVN Format Constraints Validated.")
except AssertionError:
    print("[FAIL] BVN constraint checks failed!")
    sys.exit(1)

try:
    hashed = hash_bvn("12345678901")
    assert len(hashed) == 64
    
    # Assert raise ValueError on invalid BVN
    try:
        hash_bvn("invalid-bvn")
        print("[FAIL] hash_bvn failed to raise ValueError for invalid BVN!")
        sys.exit(1)
    except ValueError:
        pass
        
    print("[OK] BVN Cryptographic Hashing (NDPR Compliance) Validated.")
except AssertionError:
    print("[FAIL] BVN hashing checks failed!")
    sys.exit(1)

# 2. Rules engine checks
try:
    engine = RuleEngine()
    tx = {
        "amount": 5000.0,
        "channel": "MOBILEAPP",
        "location": "Lagos",
        "historical_locations": ["Lagos"],
        "device_is_new": False,
        "tx_count_last_hour": 1,
        "bvn_matched": False
    }
    res = engine.evaluate(tx)
    assert "BVN_DETAILS_MISMATCH" in res["triggered_rules"]
    assert res["rule_risk_score"] >= 0.9
    assert res["rule_decision"] == "BLOCKED"
    print("[OK] BVN Mismatch Intercept Rule Validated.")
except AssertionError:
    print("[FAIL] BVN Mismatch rule check failed!")
    sys.exit(1)

try:
    tx_ussd = {
        "amount": 25000.0,
        "channel": "USSD",
        "location": "Lagos",
        "historical_locations": ["Lagos"],
        "device_is_new": False,
        "tx_count_last_hour": 1,
        "bvn_matched": True
    }
    res_ussd = engine.evaluate(tx_ussd)
    assert "USSD_SINGLE_LIMIT_EXCEEDED" in res_ussd["triggered_rules"]
    assert res_ussd["rule_decision"] == "BLOCKED"
    print("[OK] USSD Limit Enforcement Rule Validated.")
except AssertionError:
    print("[FAIL] USSD limit rule check failed!")
    sys.exit(1)

print("=========================================")
print("[SUCCESS] All core tests passed successfully!")
print("=========================================")
