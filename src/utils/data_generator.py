"""
Synthetic Nigerian bank transaction data generator.
Simulates realistic transactions for training models and demo dashboard testing.
"""

import random
from datetime import datetime, timedelta

CITIES = ["Lagos", "Abuja", "Port Harcourt", "Kano", "Enugu", "Ibadan", "Kaduna"]
CHANNELS = ["USSD", "WEB", "MOBILEAPP", "POS", "ATM"]
BANKS = ["011", "033", "044", "057", "058", "070", "214"]

def generate_synthetic_transactions(count: int = 200) -> list:
    """
    Generates a list of synthetic transaction logs with built-in normal
    behaviors and injected fraud scenarios.
    """
    transactions = []
    base_time = datetime.now() - timedelta(days=5)

    for i in range(count):
        is_fraud = random.random() < 0.05  # 5% fraud rate
        tx_time = base_time + timedelta(minutes=random.randint(5, 3600 * 2))
        
        # Base normal transaction
        tx = {
            "transaction_id": f"TXN{100000 + i}",
            "amount": round(random.uniform(500, 45000), 2),
            "channel": random.choice(CHANNELS),
            "location": random.choice(CITIES[:3]), # Lagos, Abuja, PH mostly
            "historical_locations": ["Lagos", "Abuja", "Port Harcourt"],
            "device_is_new": False,
            "tx_count_last_hour": random.randint(0, 2),
            "bvn_matched": True,
            "timestamp": tx_time.isoformat(),
            "sender_bank": random.choice(BANKS),
            "sender_nuban": f"00{random.randint(10000000, 99999999)}",
            "recipient_bank": random.choice(BANKS),
            "recipient_nuban": f"00{random.randint(10000000, 99999999)}",
            "is_fraud_label": False
        }

        # Inject Fraud Scenarios
        if is_fraud:
            tx["is_fraud_label"] = True
            scenario = random.randint(1, 4)
            
            if scenario == 1:
                # Late night high transfer drain
                tx["amount"] = round(random.uniform(600000, 2500000), 2)
                night_time = tx_time.replace(hour=random.choice([0, 1, 2, 3]))
                tx["timestamp"] = night_time.isoformat()
                tx["channel"] = "MOBILEAPP"
            
            elif scenario == 2:
                # USSD transfer limit bypass attempt
                tx["amount"] = round(random.uniform(30000, 150000), 2)
                tx["channel"] = "USSD"
            
            elif scenario == 3:
                # Out of area location hijack
                tx["location"] = "London"  # Out of Nigeria
                tx["historical_locations"] = ["Lagos", "Ibadan"]
                tx["amount"] = round(random.uniform(150000, 400000), 2)
            
            elif scenario == 4:
                # Velocity attack (smurfing/split transfers)
                tx["tx_count_last_hour"] = random.randint(6, 12)
                tx["amount"] = round(random.uniform(10000, 19000), 2)
                tx["channel"] = "USSD"

        transactions.append(tx)

    return transactions
