"""
NairaShield REST API Service.
Endpoints:
- POST /predict: Evaluates a transaction record, returns fraud probability + SHAP explanations.
- GET /health: Status indicator to confirm service availability.
Supports both Flask and pure-Python http.server fallbacks.
"""

import os
import json
import sys
import math
import datetime
from functools import wraps
import jwt

# --- CHECK DEPENDENCIES ---
try:
    import pandas as pd
    import numpy as np
    import joblib
    import xgboost as xgb
    import shap
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# --- ALERT NOTIFIER (Email + SMS dispatch) ---
try:
    from alert_notifier import AlertNotifier
    _api_notifier = AlertNotifier()
except Exception:
    _api_notifier = None

import random as _random

# --- REDIS INTEGRATION ---
redis_client = None
REDIS_HOST = os.environ.get("REDIS_HOST")
if REDIS_HOST:
    try:
        import redis
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=REDIS_HOST, port=redis_port, db=0, decode_responses=True)
        print(f"[Redis Cache] Connected to Redis at {REDIS_HOST}:{redis_port}")
    except Exception as e:
        print(f"[Warning] Failed to initialize Redis connection: {e}. Falling back to alerts_log.json")




# =====================================================================
# GLOBAL AUTHENTICATION & CONFIGURATION DATA
# =====================================================================

# Persistent user database logic
USERS_JSON_PATH = "users.json"

def load_users():
    default_users = {
        "admin": {"password": "admin123", "role": "Admin"},
        "analyst": {"password": "analyst123", "role": "Analyst"},
        "viewer": {"password": "viewer123", "role": "Viewer"}
    }
    if not os.path.exists(USERS_JSON_PATH):
        try:
            with open(USERS_JSON_PATH, "w") as f:
                json.dump(default_users, f, indent=4)
            return default_users
        except Exception:
            return default_users
    try:
        with open(USERS_JSON_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return default_users

def save_users(users):
    try:
        with open(USERS_JSON_PATH, "w") as f:
            json.dump(users, f, indent=4)
        return True
    except Exception:
        return False

# Initialize user database
USERS_DB = load_users()

# In-memory revoked tokens (blacklist)
revoked_tokens = set()

# Secret keys for signing JWTs
JWT_SECRET_KEY = "nairashield-secure-jwt-key"
JWT_REFRESH_SECRET_KEY = "nairashield-secure-refresh-key"
ALGORITHM = "HS256"

# Application global configuration
app_config = {
    "fraud_threshold": 0.5
}


# =====================================================================
# INFERENCE LOGIC WITH SHAP EXPLANATION
# =====================================================================

def perform_prediction(record: dict) -> dict:
    """
    Takes a single transaction record, runs it through the XGBoost model,
    and returns probability, prediction, and SHAP value explanations.
    """
    model_file = "xgboost_model_tuned.joblib"
    if not os.path.exists(model_file):
        model_file = "xgboost_model.joblib"
    
    # 1. Feature names template matching the processed dataset (13 features)
    feature_names = [
        "amount", 
        "channel_CARD_HOST", 
        "channel_CARD_PHONE", 
        "channel_CARD_RECURRING", 
        "channel_CARD_STORE", 
        "channel_CARD_WEB", 
        "channel_CASH_IN", 
        "channel_CASH_OUT", 
        "channel_DEBIT", 
        "channel_PAYMENT", 
        "channel_TRANSFER", 
        "source_dataset_IEEE-CIS", 
        "source_dataset_PaySim"
    ]
    
    # Align and parse inputs
    parsed_record = {}
    for f in feature_names:
        parsed_record[f] = float(record.get(f, 0.0))

    if ML_AVAILABLE and os.path.exists(model_file):
        try:
            # Convert single record to DataFrame
            df_item = pd.DataFrame([parsed_record], columns=feature_names)
            
            # Load model
            model = joblib.load(model_file)
            
            # Predict probability
            prob = float(model.predict_proba(df_item)[0, 1])
            prediction = 1 if prob >= app_config["fraud_threshold"] else 0
            
            # Compute SHAP TreeExplainer values
            explainer = shap.TreeExplainer(model)
            shap_values = explainer(df_item)
            
            # Extract SHAP parameters
            base_val = float(explainer.expected_value)
            # actual SHAP values for features
            shap_map = {}
            for col, val in zip(feature_names, shap_values.values[0]):
                shap_map[col] = float(val)
                
            return {
                "fraud_probability": round(prob, 4),
                "prediction": prediction,
                "engine": f"XGBoost ({'Tuned' if 'tuned' in model_file else 'Baseline'}) + SHAP TreeExplainer",
                "explanation": {
                    "base_value": round(base_val, 4),
                    "final_value": round(float(shap_values.values[0].sum() + base_val), 4),
                    "shap_values": shap_map
                }
            }
        except Exception as e:
            # In case of ML pipeline errors, degrade gracefully to custom fallback
            print(f"[Warning] ML inference failed: {e}. Falling back to rule-based engine.")

    # --- PURE PYTHON FALLBACK INFERENCE ENGINE ---
    # Custom rule-based probability model mirroring the mock parameters
    amount = parsed_record.get("amount", 0.0)
    is_transfer = int(parsed_record.get("channel_TRANSFER", 0.0))
    is_paysim = int(parsed_record.get("source_dataset_PaySim", 0.0))
    is_debit = int(parsed_record.get("channel_DEBIT", 0.0))
    is_card_web = int(parsed_record.get("channel_CARD_WEB", 0.0))
    is_cash_out = int(parsed_record.get("channel_CASH_OUT", 0.0))
    
    # Base Log-Odds = -1.25 (probability ~ 22%)
    base_val = -1.25
    shap_vals = {
        "amount": round(amount * 2.11, 4),
        "channel_CARD_HOST": 0.0,
        "channel_CARD_PHONE": 0.0,
        "channel_CARD_RECURRING": 0.0,
        "channel_CARD_STORE": 0.0,
        "channel_CARD_WEB": -0.25 if is_card_web == 0 else 0.45,
        "channel_CASH_IN": 0.0,
        "channel_CASH_OUT": 0.50 if is_cash_out == 1 else -0.20,
        "channel_DEBIT": 0.20 if is_debit == 0 else -0.50,
        "channel_PAYMENT": 0.0,
        "channel_TRANSFER": 0.75 if is_transfer == 1 else -0.30,
        "source_dataset_IEEE-CIS": 0.0,
        "source_dataset_PaySim": 0.40 if is_paysim == 1 else -0.10
    }
    
    final_log_odds = base_val + sum(shap_vals.values())
    # Sigmoid function to map log-odds to probability
    prob = 1.0 / (1.0 + math.exp(-final_log_odds))
    prediction = 1 if prob >= app_config["fraud_threshold"] else 0
    
    return {
        "fraud_probability": round(prob, 4),
        "prediction": prediction,
        "engine": "NairaShield Fallback Classifier + SHAP Simulator",
        "explanation": {
            "base_value": base_val,
            "final_value": round(final_log_odds, 4),
            "shap_values": shap_vals
        }
    }


# =====================================================================
# SERVER RUNNERS: FLASK VS HTTP.SERVER
# =====================================================================

if FLASK_AVAILABLE:
    app = Flask(__name__)

    # JWT generation helper functions
    def create_access_token(username, role):
        payload = {
            "sub": username,
            "role": role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
            "iat": datetime.datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)

    def create_refresh_token(username):
        payload = {
            "sub": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
            "iat": datetime.datetime.utcnow()
        }
        return jwt.encode(payload, JWT_REFRESH_SECRET_KEY, algorithm=ALGORITHM)

    # Middleware: Auth token verification decorator
    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                auth_header = request.headers['Authorization']
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
            
            if not token:
                return jsonify({"error": "Token is missing"}), 401
                
            if token in revoked_tokens:
                return jsonify({"error": "Token has been revoked"}), 401
                
            try:
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
                current_user = {
                    "username": payload["sub"],
                    "role": payload.get("role")
                }
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token has expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Token is invalid"}), 401
                
            return f(current_user, *args, **kwargs)
        return decorated

    # Middleware: Role authorization decorator
    def require_roles(allowed_roles):
        def decorator(f):
            @wraps(f)
            def decorated(current_user, *args, **kwargs):
                if current_user["role"] not in allowed_roles:
                    return jsonify({"error": f"Role '{current_user['role']}' is unauthorized to access this resource"}), 403
                return f(current_user, *args, **kwargs)
            return decorated
        return decorator

    # --- PUBLIC ROUTES ---
    @app.route('/', methods=['GET'])
    def index():
        try:
            with open("index.html", "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error loading index.html: {str(e)}", 500

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        try:
            data = request.get_json(force=True) or {}
            username = data.get("username")
            password = data.get("password")
            
            if not username or not password:
                return jsonify({"error": "Username and password are required"}), 400
                
            users = load_users()
            user = users.get(username)
            if not user or user["password"] != password:
                return jsonify({"error": "Invalid username or password"}), 401
                
            access_token = create_access_token(username, user["role"])
            refresh_token = create_refresh_token(username)
            
            return jsonify({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "username": username,
                "role": user["role"]
            })
        except Exception as e:
            return jsonify({"error": f"Authentication system error: {str(e)}"}), 500

    @app.route('/api/auth/register', methods=['POST'])
    def register():
        try:
            data = request.get_json(force=True) or {}
            username = data.get("username")
            password = data.get("password")
            role = data.get("role", "Viewer")  # default to Viewer role for security
            
            if not username or not password:
                return jsonify({"error": "Username and password are required"}), 400
                
            if role not in ["Admin", "Analyst", "Viewer"]:
                return jsonify({"error": "Invalid role. Must be one of Admin, Analyst, Viewer."}), 400
                
            users = load_users()
            if username in users:
                return jsonify({"error": f"Username '{username}' already in use"}), 400
                
            users[username] = {"password": password, "role": role}
            save_users(users)
            
            # Auto-generate login tokens to immediately authenticate
            access_token = create_access_token(username, role)
            refresh_token = create_refresh_token(username)
            
            return jsonify({
                "message": f"User '{username}' registered successfully.",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "username": username,
                "role": role
            }), 201
        except Exception as e:
            return jsonify({"error": f"Registration failed: {str(e)}"}), 500

    @app.route('/api/auth/logout', methods=['POST'])
    @token_required
    def logout(current_user):
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                revoked_tokens.add(token)
            return jsonify({"message": "Logged out successfully"})
        except Exception as e:
            return jsonify({"error": f"Logout failed: {str(e)}"}), 500

    @app.route('/api/auth/refresh', methods=['POST'])
    def refresh_token():
        try:
            data = request.get_json(force=True) or {}
            refresh_token = data.get("refresh_token")
            if not refresh_token:
                return jsonify({"error": "Refresh token is missing"}), 400
                
            payload = jwt.decode(refresh_token, JWT_REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            username = payload["sub"]
            users = load_users()
            user = users.get(username)
            if not user:
                return jsonify({"error": "User session no longer valid"}), 401
                
            new_access_token = create_access_token(username, user["role"])
            return jsonify({"access_token": new_access_token})
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Refresh token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Refresh token is invalid"}), 401
        except Exception as e:
            return jsonify({"error": f"Token refresh failed: {str(e)}"}), 500

    # --- PROTECTED ROLE-BASED ROUTES ---
    @app.route('/health', methods=['GET'])
    @token_required
    @require_roles(['Admin', 'Analyst', 'Viewer'])
    def health(current_user):
        return jsonify({
            "status": "healthy",
            "service": "NairaShield Fraud Detection REST API",
            "framework": "Flask",
            "requester": current_user
        })

    @app.route('/predict', methods=['POST'])
    @token_required
    @require_roles(['Admin', 'Analyst', 'Viewer'])
    def predict(current_user):
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "Missing JSON request body"}), 400

            response = perform_prediction(data)

            # === FRAUD ALERT NOTIFICATION & LOGGING ===
            # Log and notify if transaction is flagged as fraud (prediction == 1)
            if response.get("prediction") == 1:
                fp = response.get("fraud_probability", 0.0)
                try:
                    shap_vals = response.get("explanation", {}).get("shap_values", {})
                    alert_payload = {
                        "alert_id": f"API-ALT-{_random.randint(100000, 999999)}",
                        "transaction_id": data.get("transaction_id", f"TXN-{_random.randint(10000, 99999)}"),
                        "amount": float(data.get("amount", 0.0)),
                        "channel": next(
                            (k.replace("channel_", "") for k, v in data.items()
                             if k.startswith("channel_") and float(v or 0) == 1.0),
                            "UNKNOWN"
                        ),
                        "location": data.get("location", "API Request"),
                        "timestamp": datetime.datetime.now().isoformat(),
                        "model_probability": fp,
                        "rule_risk_score": fp,  # mirror for API-only predictions
                        "triggered_rules": ["MODEL_HIGH_FRAUD_RISK"] if fp >= 0.85 else ["MODEL_SUSPICIOUS_RISK"],
                        "shap_values": shap_vals,
                        "status": "BLOCKED" if fp >= 0.80 else "PENDING_OTP"
                    }
                    
                    # Dispatch to SMS/Email notifier if it is critical (>= 85%)
                    if _api_notifier is not None and fp >= 0.85:
                        _api_notifier.dispatch(alert_payload)
                        
                    # Log the alert to Redis or alerts_log.json
                    if redis_client:
                        try:
                            redis_client.rpush("nairashield:alerts", json.dumps(alert_payload))
                            redis_client.ltrim("nairashield:alerts", -100, -1)
                        except Exception as re_err:
                            print(f"[Error] Failed to write API alert to Redis: {re_err}")
                    else:
                        log_data = []
                        if os.path.exists("alerts_log.json"):
                            try:
                                with open("alerts_log.json", "r") as f:
                                    log_data = json.load(f)
                            except Exception:
                                log_data = []
                        log_data.append(alert_payload)
                        try:
                            with open("alerts_log.json", "w") as f:
                                json.dump(log_data, f, indent=4)
                        except Exception as wr_err:
                            print(f"[Error] Failed to write API alert to file: {wr_err}")
                except Exception as notify_err:
                    print(f"[Notifier/Logger] Error processing alert: {notify_err}")

            return jsonify(response)
        except Exception as e:
            return jsonify({"error": f"Internal prediction failure: {str(e)}"}), 500


    @app.route('/api/transactions', methods=['GET'])
    @token_required
    @require_roles(['Admin', 'Analyst', 'Viewer'])
    def get_transactions(current_user):
        alerts = []
        if redis_client:
            try:
                redis_alerts = redis_client.lrange("nairashield:alerts", 0, -1)
                # Seed Redis from alerts_log.json if Redis list is empty but file has data
                if not redis_alerts and os.path.exists("alerts_log.json"):
                    try:
                        with open("alerts_log.json", "r") as f:
                            local_alerts = json.load(f)
                        if local_alerts:
                            redis_client.delete("nairashield:alerts")
                            redis_client.rpush("nairashield:alerts", *[json.dumps(a) for a in local_alerts])
                            redis_alerts = redis_client.lrange("nairashield:alerts", 0, -1)
                    except Exception as se:
                        print(f"[Warning] Failed to seed Redis with alerts_log.json: {se}")
                alerts = [json.loads(a) for a in redis_alerts]
            except Exception as e:
                print(f"[Error] Failed to read alerts from Redis: {e}. Falling back to alerts_log.json")
                if os.path.exists("alerts_log.json"):
                    try:
                        with open("alerts_log.json", "r") as f:
                            alerts = json.load(f)
                    except Exception as fe:
                        print(f"[Error] Failed to read alerts log: {fe}")
        else:
            if os.path.exists("alerts_log.json"):
                try:
                    with open("alerts_log.json", "r") as f:
                        alerts = json.load(f)
                except Exception as e:
                    print(f"[Error] Failed to read alerts log: {e}")
        return jsonify({"transactions": alerts})

    @app.route('/api/flag', methods=['POST'])
    @token_required
    @require_roles(['Admin', 'Analyst'])
    def flag_transaction(current_user):
        try:
            data = request.get_json(force=True) or {}
            alert_id = data.get("alert_id")
            action = data.get("action", "BLOCKED")
            
            if not alert_id:
                return jsonify({"error": "Missing alert_id"}), 400
                
            success = False
            
            if redis_client:
                try:
                    redis_alerts = redis_client.lrange("nairashield:alerts", 0, -1)
                    alerts = [json.loads(a) for a in redis_alerts]
                    
                    for alert in alerts:
                        if alert.get("alert_id") == alert_id:
                            alert["status"] = action
                            alert["flagged_by"] = current_user["username"]
                            alert["flagged_at"] = datetime.datetime.utcnow().isoformat()
                            success = True
                            break
                            
                    if success:
                        pipe = redis_client.pipeline()
                        pipe.delete("nairashield:alerts")
                        pipe.rpush("nairashield:alerts", *[json.dumps(a) for a in alerts])
                        pipe.execute()
                except Exception as e:
                    print(f"[Error] Redis flag update failed: {e}. Trying fallback to alerts_log.json")
                    success = False
                    
            if not success or not redis_client:
                if os.path.exists("alerts_log.json"):
                    try:
                        with open("alerts_log.json", "r") as f:
                            alerts = json.load(f)
                        for alert in alerts:
                            if alert.get("alert_id") == alert_id:
                                alert["status"] = action
                                alert["flagged_by"] = current_user["username"]
                                alert["flagged_at"] = datetime.datetime.utcnow().isoformat()
                                success = True
                                break
                        if success:
                            with open("alerts_log.json", "w") as f:
                                json.dump(alerts, f, indent=4)
                    except Exception as e:
                        return jsonify({"error": f"Failed to modify alerts log: {str(e)}"}), 500
                        
            if success:
                return jsonify({"message": f"Alert {alert_id} flagged/blocked successfully by {current_user['username']}."})
            else:
                return jsonify({"error": f"Alert {alert_id} not found in log."}), 404
        except Exception as e:
            return jsonify({"error": f"Flagging operation failed: {str(e)}"}), 500

    @app.route('/api/admin/config', methods=['POST'])
    @token_required
    @require_roles(['Admin'])
    def update_config(current_user):
        try:
            data = request.get_json(force=True) or {}
            new_threshold = data.get("fraud_threshold")
            if new_threshold is None:
                return jsonify({"error": "Missing fraud_threshold"}), 400
                
            try:
                new_threshold = float(new_threshold)
                if not (0.0 <= new_threshold <= 1.0):
                    raise ValueError()
            except ValueError:
                return jsonify({"error": "fraud_threshold must be a float between 0.0 and 1.0"}), 400
                
            app_config["fraud_threshold"] = new_threshold
            return jsonify({
                "message": "Configuration updated successfully",
                "fraud_threshold": new_threshold,
                "updated_by": current_user["username"]
            })
        except Exception as e:
            return jsonify({"error": f"Failed to update configurations: {str(e)}"}), 500

    @app.route('/api/admin/create-user', methods=['POST'])
    @token_required
    @require_roles(['Admin'])
    def admin_create_user(current_user):
        try:
            data = request.get_json(force=True) or {}
            username = data.get("username")
            password = data.get("password")
            role = data.get("role")
            
            if not username or not password or not role:
                return jsonify({"error": "Username, password, and role are required"}), 400
                
            if role not in ["Admin", "Analyst", "Viewer"]:
                return jsonify({"error": "Role must be Admin, Analyst, or Viewer"}), 400
                
            users = load_users()
            if username in users:
                return jsonify({"error": f"Username '{username}' already exists"}), 400
                
            users[username] = {"password": password, "role": role}
            save_users(users)
            return jsonify({"message": f"User '{username}' created successfully by Admin '{current_user['username']}'."}), 201
        except Exception as e:
            return jsonify({"error": f"Failed to create user: {str(e)}"}), 500



    def start_flask_server(port=5000):
        print(f"\n[Flask Engine] Booting REST API on port {port}...")
        print("Auth Endpoints:")
        print(f"  - POST http://localhost:{port}/api/auth/login")
        print(f"  - POST http://localhost:{port}/api/auth/logout")
        print(f"  - POST http://localhost:{port}/api/auth/refresh")
        print("Protected Endpoints:")
        print(f"  - GET  http://localhost:{port}/health")
        print(f"  - POST http://localhost:{port}/predict")
        print(f"  - GET  http://localhost:{port}/api/transactions")
        print(f"  - POST http://localhost:{port}/api/flag")
        print(f"  - POST http://localhost:{port}/api/admin/config")

        app.run(host="0.0.0.0", port=port, debug=False)

else:
    # http.server fallback implementation
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class FallbackAPIHandler(BaseHTTPRequestHandler):
        def _set_headers(self, status=200):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            # Prevent CORS issues
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

        def do_OPTIONS(self):
            self._set_headers(200)

        def do_GET(self):
            parsed_path = self.path.split('?')[0]
            if parsed_path == '/' or parsed_path == '/index.html':
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    with open("index.html", "r", encoding="utf-8") as f:
                        self.wfile.write(f.read().encode('utf-8'))
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error loading index.html: {str(e)}".encode('utf-8'))
            elif parsed_path == '/health':
                self._set_headers(200)
                response = {
                    "status": "healthy",
                    "service": "NairaShield Fraud Detection REST API (Fallback Mode)",
                    "framework": "Python http.server"
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))

            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Path not found"}).encode('utf-8'))

        def do_POST(self):
            parsed_path = self.path.split('?')[0]
            if parsed_path == '/predict':
                try:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    response = perform_prediction(data)
                    self._set_headers(200)
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                except Exception as e:
                    self._set_headers(500)
                    self.wfile.write(json.dumps({"error": f"Failed to parse or predict: {str(e)}"}).encode('utf-8'))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Path not found"}).encode('utf-8'))

    def start_fallback_server(port=5000):
        print(f"\n[http.server Engine] Flask missing. Booting native fallback server on port {port}...")
        print("Test endpoints:")
        print(f"  - GET  http://localhost:{port}/health")
        print(f"  - POST http://localhost:{port}/predict")

        server = HTTPServer(("0.0.0.0", port), FallbackAPIHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down REST API server...")
            server.server_close()


if __name__ == "__main__":
    port_number = int(os.environ.get("PORT", 5000))
    if FLASK_AVAILABLE:
        start_flask_server(port_number)
    else:
        start_fallback_server(port_number)
