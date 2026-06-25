"""
Configuration settings for the NairaShield AI Fraud Detection System.
Includes limits, thresholds, and risk score weights tailored to Nigerian bank environments.
"""

import os

# Transaction Limits (in Naira)
MAX_USSD_SINGLE_LIMIT_WITHOUT_TOKEN = 20000.0  # Limit for a single USSD transaction without hardware token
MAX_USSD_DAILY_LIMIT = 100000.0                # Daily total cap on USSD transfers
MAX_MOBILE_APP_SINGLE_LIMIT_WITHOUT_TOKEN = 100000.0 # Mobile App transaction limit without hardware token

# Velocity Rules
MAX_TRANSACTIONS_PER_HOUR = 5                  # High velocity check count
MAX_SAME_BENEFICIARY_TRANSFERS_PER_HOUR = 3    # Split transaction check count

# Timing Risks
NIGHT_WINDOW_START = 23  # 11:00 PM
NIGHT_WINDOW_END = 4     # 04:00 AM

# Risk Weights for Rules (0.0 to 1.0)
WEIGHTS = {
    "bvn_mismatch": 0.90,       # BVN owner details mismatch
    "night_large_tx": 0.65,     # Large transfer done during the night
    "ussd_limit_exceeded": 0.85,# USSD limit bypass attempt
    "high_velocity": 0.70,      # Suspiciously fast transfers (smurfing/structuring)
    "location_anomaly": 0.75,   # Login/transact location mismatch
    "new_device_first_tx": 0.50 # First transaction on a newly registered device
}

# Machine Learning Settings
ML_ANOMALY_THRESHOLD = -0.15    # Isolation Forest anomaly threshold score
MOCK_DATA_SIZE = 1000           # Size of synthetic transaction logs to generate
