"""
NairaShield Real-Time Transaction Streaming Pipeline.
Simulates Apache Kafka messaging queues using Python threading and Queue structures.
Measures model scoring latency (target < 200ms) and routes flagged alerts to a separate queue.
"""

import os
import sys
import time
import json
import queue
import threading
import random
from datetime import datetime

# --- CHECK DEPENDENCIES ---
try:
    import pandas as pd
    import numpy as np
    import joblib
    import xgboost as xgb
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# --- ALERT NOTIFIER (Email + SMS dispatch) ---
try:
    from alert_notifier import AlertNotifier
    _notifier = AlertNotifier()
    NOTIFIER_AVAILABLE = True
except Exception as _notifier_err:
    NOTIFIER_AVAILABLE = False
    _notifier = None

# Fallback Console for CP1252 / Windows Cmd line compliance
class SafeConsole:
    def print(self, *args, **kwargs):
        cleaned_args = []
        for arg in args:
            arg_str = str(arg)
            import re
            cleaned = re.sub(r'\[/?\w+\s*[^\]]*\]', '', arg_str)
            cleaned = cleaned.replace('₦', 'NGN').replace('✔', '[OK]').replace('✗', '[FAIL]')
            cleaned_args.append(cleaned)
        print(*cleaned_args, **kwargs)

    def rule(self, title=""):
        print(f"\n==================== {title} ====================\n")

if RICH_AVAILABLE:
    console = Console()
else:
    console = SafeConsole()

# Import project utilities
from src.utils.data_generator import generate_synthetic_transactions
from src.rules.engine import RuleEngine

# --- REDIS INTEGRATION ---
redis_client = None
REDIS_HOST = os.environ.get("REDIS_HOST")
if REDIS_HOST:
    try:
        import redis
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=REDIS_HOST, port=redis_port, db=0, decode_responses=True)
        console.print(f"[Redis Cache] Connected to Redis at {REDIS_HOST}:{redis_port}")
    except Exception as e:
        console.print(f"[Warning] Failed to initialize Redis connection: {e}. Falling back to alerts_log.json")

# =====================================================================
# SIMULATED / REAL KAFKA BROKER TOPOLOGY
# =====================================================================

class DistributedBroker:
    """
    Handles routing message payloads to either a real Kafka Broker 
    or a simulated Python in-memory queue depending on environment configurations.
    """
    def __init__(self):
        self.simulated_topics = {
            "transactions-topic": queue.Queue(),
            "alerts-topic": queue.Queue()
        }
        self.kafka_producer = None
        self.kafka_consumer = None
        self.use_real_kafka = False
        
        self.bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
        if self.bootstrap_servers:
            try:
                from kafka import KafkaProducer, KafkaConsumer
                self.kafka_producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers.split(","),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    acks='all',
                    retries=3
                )
                
                self.kafka_consumer = KafkaConsumer(
                    "transactions-topic",
                    bootstrap_servers=self.bootstrap_servers.split(","),
                    value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                    auto_offset_reset='latest',
                    enable_auto_commit=True,
                    group_id='nairashield-group',
                    consumer_timeout_ms=500
                )
                self.use_real_kafka = True
                console.print(f"[Kafka] Connected to distributed Kafka bootstrap servers: {self.bootstrap_servers}")
            except Exception as e:
                console.print(f"[Warning] Failed to initialize real Kafka client: {e}. Falling back to simulated in-memory broker.")
                self.use_real_kafka = False

    def send(self, topic: str, message: dict):
        if self.use_real_kafka and self.kafka_producer:
            try:
                self.kafka_producer.send(topic, message)
            except Exception as e:
                console.print(f"[Warning] Failed to send message to real Kafka topic '{topic}': {e}. Storing in-memory.")
                self.simulated_topics[topic].put(message)
        else:
            if topic in self.simulated_topics:
                self.simulated_topics[topic].put(message)
            else:
                raise KeyError(f"Topic '{topic}' does not exist on simulated broker.")

    def poll(self, topic: str, timeout: float = 0.5) -> dict:
        if self.use_real_kafka and self.kafka_consumer and topic == "transactions-topic":
            try:
                # Poll from real Kafka consumer
                for message in self.kafka_consumer:
                    return message.value
                return None
            except Exception as e:
                console.print(f"[Warning] Failed to poll from real Kafka topic '{topic}': {e}. Polling in-memory.")
                try:
                    return self.simulated_topics[topic].get(timeout=timeout)
                except queue.Empty:
                    return None
        else:
            if topic in self.simulated_topics:
                try:
                    return self.simulated_topics[topic].get(timeout=timeout)
                except queue.Empty:
                    return None
            else:
                raise KeyError(f"Topic '{topic}' does not exist on simulated broker.")

# Initialize global broker instance
broker = DistributedBroker()
rule_engine = RuleEngine()

# Load XGBoost Model
MODEL_PATH = "xgboost_model_tuned.joblib"
xgb_model = None
if ML_AVAILABLE and os.path.exists(MODEL_PATH):
    try:
        xgb_model = joblib.load(MODEL_PATH)
        console.print(f"[green][OK][/green] Tuned XGBoost model loaded successfully from: {MODEL_PATH}")
    except Exception as e:
        console.print(f"[yellow][Warning][/yellow] Failed to load tuned model: {e}. Falling back to Rule Engine + Simulated inference.")
else:
    console.print(f"[yellow][Warning][/yellow] Tuned model '{MODEL_PATH}' missing. Running fallback prediction engine.")

# =====================================================================
# FEATURE PREPROCESSING UTILITY
# =====================================================================

def preprocess_for_model(tx: dict) -> pd.DataFrame:
    """
    Transforms the raw generated transaction dict into the 13-feature DataFrame
    expected by the trained XGBoost model.
    """
    amount = tx.get("amount", 0.0)
    # Scale amount (assuming training set max range is ~2.5 million NGN)
    norm_amount = min(amount / 2500000.0, 1.0)
    
    channel = tx.get("channel", "MOBILEAPP").upper()
    
    # Map channels to one-hot columns:
    # CHANNELS are ["USSD", "WEB", "MOBILEAPP", "POS", "ATM"]
    channel_mapping = {
        "USSD": "channel_TRANSFER",
        "MOBILEAPP": "channel_TRANSFER",
        "WEB": "channel_CARD_WEB",
        "POS": "channel_CASH_OUT",
        "ATM": "channel_CASH_OUT"
    }
    mapped_channel = channel_mapping.get(channel, "channel_TRANSFER")
    
    feature_dict = {
        "amount": norm_amount,
        "channel_CARD_HOST": 1 if mapped_channel == "channel_CARD_HOST" else 0,
        "channel_CARD_PHONE": 1 if mapped_channel == "channel_CARD_PHONE" else 0,
        "channel_CARD_RECURRING": 1 if mapped_channel == "channel_CARD_RECURRING" else 0,
        "channel_CARD_STORE": 1 if mapped_channel == "channel_CARD_STORE" else 0,
        "channel_CARD_WEB": 1 if mapped_channel == "channel_CARD_WEB" else 0,
        "channel_CASH_IN": 1 if mapped_channel == "channel_CASH_IN" else 0,
        "channel_CASH_OUT": 1 if mapped_channel == "channel_CASH_OUT" else 0,
        "channel_DEBIT": 1 if mapped_channel == "channel_DEBIT" else 0,
        "channel_PAYMENT": 1 if mapped_channel == "channel_PAYMENT" else 0,
        "channel_TRANSFER": 1 if mapped_channel == "channel_TRANSFER" else 0,
        "source_dataset_IEEE-CIS": 0,
        "source_dataset_PaySim": 1
    }
    
    return pd.DataFrame([feature_dict])

# =====================================================================
# STREAM PRODUCER THREAD
# =====================================================================

class TransactionProducer(threading.Thread):
    """
    Generates synthetic NairaShield transactions or streams pre-loaded sample records in real-time.
    Pushes messages onto the 'transactions-topic' queue.
    """
    def __init__(self, limit: int = 50, sample_transactions: list = None):
        super().__init__()
        self.daemon = True
        self.limit = limit
        self.sample_transactions = sample_transactions
        self.running = True

    def run(self):
        console.print("[blue][Producer][/blue] Starting Real-time Transaction Stream Producer...")
        count = 0
        while self.running and (self.limit < 0 or count < self.limit):
            tx = None
            if self.sample_transactions and count < len(self.sample_transactions):
                tx = self.sample_transactions[count]
                # Update production timestamps
                tx["produce_time"] = time.time()
                tx["timestamp"] = datetime.now().isoformat()
            else:
                # 1. Generate single synthetic transaction
                tx_list = generate_synthetic_transactions(count=1)
                if tx_list:
                    tx = tx_list[0]
                    tx["produce_time"] = time.time()
            
            if tx:
                # 2. Push message to queue
                broker.send("transactions-topic", tx)
                count += 1
                
            # Sleep random interval (e.g. 150ms - 450ms) to simulate streaming
            time.sleep(random.uniform(0.15, 0.45))
            
        console.print(f"[blue][Producer][/blue] Finished streaming {count} transactions.")

# =====================================================================
# STREAM CONSUMER & EVALUATOR THREAD
# =====================================================================

class FraudConsumer(threading.Thread):
    """
    Pulls messages from the 'transactions-topic' queue, preprocesses features,
    scores the transactions using the tuned XGBoost model, verifies latency,
    and routes suspicious transactions to 'alerts-topic'.
    """
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.processed_count = 0
        self.anomaly_count = 0
        self.latency_records = []

    def run(self):
        console.print("[green][Consumer][/green] Booting Real-time Fraud Detection Scoring Engine...")
        while self.running:
            # Poll from queue
            tx = broker.poll("transactions-topic", timeout=0.5)
            if not tx:
                continue
                
            # 1. Start scoring latency timer
            start_time = time.perf_counter()
            
            # 2. Run rules evaluation
            rule_res = rule_engine.evaluate(tx)
            
            # 3. Preprocess and predict using XGBoost (if available)
            fraud_prob = 0.0
            prediction = 0
            engine_name = "NairaShield Fallback + Rules Engine"
            
            shap_values_dict = {}  # Populated if SHAP model is available
            if ML_AVAILABLE and xgb_model is not None:
                try:
                    features_df = preprocess_for_model(tx)
                    # Predict probability
                    prob = float(xgb_model.predict_proba(features_df)[0, 1])
                    fraud_prob = round(prob, 4)
                    prediction = 1 if prob >= 0.5 else 0
                    engine_name = "Tuned XGBoost Engine"
                    # Extract SHAP values for alert explanations
                    try:
                        import shap as shap_lib
                        explainer = shap_lib.TreeExplainer(xgb_model)
                        sv = explainer.shap_values(features_df)
                        shap_values_dict = {
                            col: float(sv[0][i])
                            for i, col in enumerate(features_df.columns)
                        }
                    except Exception:
                        pass  # SHAP not available; alerts still dispatch without explanations
                except Exception as e:
                    # Graceful degradation
                    pass

            if engine_name == "NairaShield Fallback + Rules Engine":
                # Simulated inference based on rule risk level
                fraud_prob = rule_res["rule_risk_score"]
                prediction = 1 if fraud_prob >= 0.50 else 0
                
            # 4. Stop latency timer (in milliseconds)
            end_time = time.perf_counter()
            scoring_latency_ms = (end_time - start_time) * 1000
            self.latency_records.append(scoring_latency_ms)
            
            # 5. Determine if transaction is anomalous
            is_anomaly = False
            flagged_reasons = []
            
            # Flag if model probability is high or if rules block/flag it
            if prediction == 1 or fraud_prob >= 0.50:
                is_anomaly = True
                flagged_reasons.append(f"Model Probability: {fraud_prob * 100:.1f}%")
            if rule_res["rule_decision"] in ["BLOCKED", "PENDING_OTP"]:
                is_anomaly = True
                flagged_reasons.extend(rule_res["triggered_rules"])
                
            self.processed_count += 1
            
            # Display real-time output
            latency_color = "green" if scoring_latency_ms < 200 else "red"
            decision_text = f"[green]APPROVED[/green]"
            if is_anomaly:
                decision_text = f"[red]FLAGGED (Risk: {max(fraud_prob, rule_res['rule_risk_score'])*100:.0f}%)[/red]"
                
            console.print(
                f"[Consumer] Tx {tx['transaction_id']} | "
                f"Amount: NGN {tx['amount']:,} | "
                f"Scoring Latency: [{latency_color}]{scoring_latency_ms:.2f}ms[/{latency_color}] | "
                f"Decision: {decision_text} ({engine_name})"
            )
            
            # 6. Route anomalies to separate Alert Queue
            if is_anomaly:
                self.anomaly_count += 1
                alert_message = {
                    "alert_id": f"ALT{random.randint(100000, 999999)}",
                    "transaction_id": tx["transaction_id"],
                    "amount": tx["amount"],
                    "channel": tx["channel"],
                    "location": tx["location"],
                    "model_probability": fraud_prob,
                    "rule_risk_score": rule_res["rule_risk_score"],
                    "triggered_rules": rule_res["triggered_rules"],
                    "scoring_latency_ms": round(scoring_latency_ms, 3),
                    "timestamp": datetime.now().isoformat(),
                    "shap_values": shap_values_dict  # empty dict when ML unavailable
                }
                broker.send("alerts-topic", alert_message)
                
            # Yield slice
            time.sleep(0.01)

# =====================================================================
# ALERT HANDLER & LOGGER THREAD
# =====================================================================

class AlertLogger(threading.Thread):
    """
    Subscribes to 'alerts-topic' and logs alerts to an external JSON file
    while formatting real-time warnings on screen.
    """
    def __init__(self, output_file: str = "alerts_log.json"):
        super().__init__()
        self.daemon = True
        self.running = True
        self.output_file = output_file
        # Initialize/clear file only if Redis is not active
        if not redis_client:
            try:
                with open(self.output_file, "w") as f:
                    f.write("[]")
            except Exception:
                pass

    def run(self):
        console.print("[red][Alert Logger][/red] Starting Real-time Alert Consumer logger...")
        while self.running:
            alert = broker.poll("alerts-topic", timeout=0.5)
            if not alert:
                continue
                
            # Log to Redis if available, else JSON
            logged_to_redis = False
            if redis_client:
                try:
                    redis_client.rpush("nairashield:alerts", json.dumps(alert))
                    # Keep only the last 100 alerts in Redis to avoid unbounded growth
                    redis_client.ltrim("nairashield:alerts", -100, -1)
                    logged_to_redis = True
                except Exception as e:
                    console.print(f"[Warning] Failed to write alert to Redis: {e}. Falling back to alerts_log.json")
            
            if not logged_to_redis:
                try:
                    if os.path.exists(self.output_file):
                        with open(self.output_file, "r") as f:
                            data = json.load(f)
                    else:
                        data = []
                    data.append(alert)
                    with open(self.output_file, "w") as f:
                        json.dump(data, f, indent=4)
                except Exception as e:
                    console.print(f"[red][Error][/red] Failed to write alert to file: {e}")

            # === EMAIL + SMS NOTIFICATION ===
            # Dispatch multi-channel notification if confidence >= threshold (default 85%)
            if NOTIFIER_AVAILABLE and _notifier is not None:
                try:
                    delivery = _notifier.dispatch(alert)
                    if delivery["threshold_met"]:
                        status_parts = []
                        if delivery["email_sent"]:
                            status_parts.append("Email=SENT")
                        else:
                            status_parts.append("Email=SKIPPED (check .env)")
                        if delivery["sms_sent"]:
                            status_parts.append("SMS=SENT")
                        else:
                            status_parts.append("SMS=SKIPPED (check .env)")
                        notify_status = " | ".join(status_parts)
                        console.print(
                            f"[Notifier] Alert {alert['alert_id']} dispatched "
                            f"({delivery['confidence']*100:.1f}% confidence) -> {notify_status}"
                        )
                except Exception as notify_err:
                    console.print(f"[Error][Notifier] {notify_err}")

            # Format visual alert panel
            if RICH_AVAILABLE:
                alert_panel = Panel(
                    f"[bold red]CRITICAL ALERT INTERCEPTED[/bold red]\n"
                    f"Alert ID: {alert['alert_id']} | Tx ID: {alert['transaction_id']}\n"
                    f"Amount  : NGN {alert['amount']:,} | Channel: {alert['channel']} | Location: {alert['location']}\n"
                    f"Model Prob: {alert['model_probability']*100:.1f}% | Rules Risk: {alert['rule_risk_score']*100:.1f}%\n"
                    f"Triggered: {', '.join(alert['triggered_rules']) if alert['triggered_rules'] else 'None'}\n"
                    f"Latency : {alert['scoring_latency_ms']:.2f}ms [green](ROUTED TO ALERT QUEUE)[/green]",
                    border_style="red",
                    title="NairaShield Threat Center"
                )
                console.print(alert_panel)
            else:
                console.print(
                    f"\n!!! [ALERT] Tx {alert['transaction_id']} (NGN {alert['amount']:,}) flagged. "
                    f"Rules triggered: {alert['triggered_rules']}. "
                    f"Model Probability: {alert['model_probability'] * 100:.1f}%. "
                    f"Scoring Latency: {alert['scoring_latency_ms']:.2f}ms. Routed to alert queue.\n"
                )
                
            time.sleep(0.01)

# =====================================================================
# RUN CONTROL & VERIFICATION
# =====================================================================

def run_real_time_stream(sample_transactions: list = None):
    console.rule("[bold cyan]NairaShield Real-Time Streaming Verification[/bold cyan]")
    
    # Setup threads
    limit = len(sample_transactions) if sample_transactions else 25
    producer = TransactionProducer(limit=limit, sample_transactions=sample_transactions)
    consumer = FraudConsumer()
    logger = AlertLogger()

    # Start threads
    logger.start()
    consumer.start()
    producer.start()

    # Wait for producer to finish streaming
    producer.join()
    
    # Wait for consumer to empty topic
    time.sleep(1.5)
    
    # Shutdown consumer and logger threads
    consumer.running = False
    logger.running = False
    
    consumer.join()
    logger.join()
    
    console.rule("[bold green]Streaming Verification Completed[/bold green]")
    
    # Output metrics
    total_tx = consumer.processed_count
    anomalies = consumer.anomaly_count
    latencies = consumer.latency_records
    
    avg_latency = np.mean(latencies) if latencies else 0.0
    max_latency = np.max(latencies) if latencies else 0.0
    p95_latency = np.percentile(latencies, 95) if latencies else 0.0
    
    headers = ["Metric Description", "Value", "Latency Target Check"]
    widths = {h: len(h) for h in headers}
    
    # Generate verification table
    latency_status = "PASS (< 200ms)" if avg_latency < 200 else "FAIL (> 200ms)"
    p95_status = "PASS (< 200ms)" if p95_latency < 200 else "FAIL (> 200ms)"
    
    results = [
        ("Total Streamed Transactions", f"{total_tx}", "N/A"),
        ("Flagged Fraud & Routed Alerts", f"{anomalies}", "N/A"),
        ("Average Processing Latency", f"{avg_latency:.3f} ms", latency_status),
        ("95th Percentile Latency", f"{p95_latency:.3f} ms", p95_status),
        ("Peak Processing Latency", f"{max_latency:.3f} ms", "N/A")
    ]
    
    # Print metrics table
    if RICH_AVAILABLE:
        table = Table(title="Streaming Simulation Performance Metrics", border_style="cyan")
        table.add_column("Metric Description", style="cyan")
        table.add_column("Value", style="yellow", justify="right")
        table.add_column("Latency Target Check", style="green" if avg_latency < 200 else "red")
        
        for desc, val, status in results:
            table.add_row(desc, val, status)
        console.print(table)
    else:
        # Standard ASCII format
        widths = {"desc": 30, "val": 15, "status": 20}
        border = "+" + "+".join("-" * (widths[k] + 2) for k in widths) + "+"
        print(border)
        print(f"| {'Metric Description'.ljust(widths['desc'])} | {'Value'.rjust(widths['val'])} | {'Latency Target Check'.ljust(widths['status'])} |")
        print(border)
        for desc, val, status in results:
            print(f"| {desc.ljust(widths['desc'])} | {val.rjust(widths['val'])} | {status.ljust(widths['status'])} |")
        print(border)
        
    console.print(f"[green][OK][/green] Alerts log saved locally to: alerts_log.json\n")

if __name__ == "__main__":
    if os.environ.get("STREAM_CONTINUOUS", "false").lower() == "true":
        console.rule("[bold cyan]NairaShield Real-Time Streaming Daemon[/bold cyan]")
        producer = TransactionProducer(limit=-1)
        consumer = FraudConsumer()
        logger = AlertLogger()

        logger.start()
        consumer.start()
        producer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("[blue][System][/blue] Shutting down NairaShield stream daemon...")
            producer.running = False
            consumer.running = False
            logger.running = False
            producer.join()
            consumer.join()
            logger.join()
    else:
        run_real_time_stream()
