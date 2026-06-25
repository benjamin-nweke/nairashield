"""
Unit tests for CBN NUBAN validation and BVN format checker.
"""

import pytest
from src.utils.nuban import validate_nuban, validate_bvn, hash_bvn

def test_valid_nuban():
    # GTBank code is 058.
    # Serial is 011000000.
    # Combined: 058011000000
    # Weighted sum: 0*3 + 5*7 + 8*3 + 0*3 + 1*7 + 1*3 + 0*3 + 0*7 + 0*3 + 0*3 + 0*7 + 0*3 = 69
    # 69 % 10 = 9
    # Check digit = 10 - 9 = 1.
    # Account: 0110000001
    assert validate_nuban("0110000001", "058") is True

def test_invalid_nuban():
    # Wrong check digit
    assert validate_nuban("0110000002", "058") is False
    # Non digit
    assert validate_nuban("011000000a", "058") is False
    # Wrong length
    assert validate_nuban("011000000", "058") is False

def test_bvn_validation():
    # BVN must be 11 digits
    assert validate_bvn("12345678901") is True
    assert validate_bvn("12345") is False
    assert validate_bvn("abcdefghijk") is False

def test_bvn_hashing():
    bvn = "12345678901"
    hashed = hash_bvn(bvn)
    assert len(hashed) == 64  # SHA-256 is 64 hex characters
    with pytest.raises(ValueError):
        hash_bvn("invalid-bvn")
