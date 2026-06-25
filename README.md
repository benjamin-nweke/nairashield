# NairaShield AI 🇳🇬🛡️
### AI-Based Fraud Detection System for Nigerian Banks

NairaShield AI is an intelligent transaction monitoring and fraud detection system designed specifically for the Nigerian banking ecosystem. It combines Central Bank of Nigeria (CBN) regulatory rules, transaction velocity limits, and machine learning anomaly detection to protect accounts from common threat vectors (such as SIM-swap draining, USSD limit bypass, and unauthorized late-night transfers).

---

## 🚀 Entry Point: Custom Antigravity Module
To demonstrate standard Python library override mechanics, this project utilizes a custom `antigravity.py` module as its entry point. 

When you run the system, it imports `antigravity`, which displays a gorgeous, dynamic Nigerian-themed system boot screen before launching the main security command-line dashboard.

### How to Run:
Ensure you have installed the dependencies:
```bash
pip install -r requirements.txt
```

Launch the security console:
```bash
python run.py
```
*(Or import `antigravity` inside any Python environment or REPL from the root folder)*

---

## 📂 Folder & File Role Directory

Here is the role of each directory and file in the project:

### 1. `config/`
Stores configurable system thresholds, limits, and risk weights.
*   **[settings.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/config/settings.py)**: Defines variables like the USSD transfer limit without token (`20,000 NGN`), the nightly high-risk transaction window (`11 PM to 4 AM`), and threat-specific weights (e.g., `0.90` for BVN mismatches).

### 2. `data/`
Intended for database files, trained models, or CSV transaction dumps.
*   *Note: Real-world models would serialize their weights here.*

### 3. `src/` (Core Application)
Houses the logic, models, rules, and validators of NairaShield.
*   **[app.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/src/app.py)**: Coordinates the interactive CLI terminal. Allows bank operators to check individual transactions, run batch simulations, retrain models, inspect risk parameters, and validate accounts.
*   **`src/models/`**:
    *   **[anomaly_detector.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/src/models/anomaly_detector.py)**: Preprocesses transactions and feeds them into a `scikit-learn` Isolation Forest model to flag behavioral anomalies. Includes a robust statistical Z-score fallback if ML libraries are missing.
*   **`src/rules/`**:
    *   **[engine.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/src/rules/engine.py)**: Runs deterministic checks based on Nigerian banking standards (e.g., USSD transfer limits, midnight high-value transfers, new device registrations, and BVN mismatches).
*   **`src/utils/`**:
    *   **[nuban.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/src/utils/nuban.py)**: Implements the official CBN **NUBAN (Nigerian Uniform Bank Account Number)** 12-digit weighted check-digit validation algorithm and BVN structure checks.
    *   **[data_generator.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/src/utils/data_generator.py)**: Simulates realistic Nigerian transaction logs with normal patterns (e.g., Lagos POS retail purchases) and injected fraud signatures.

### 4. `tests/`
Houses test suites for verification of security logic.
*   **[test_nuban.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/tests/test_nuban.py)**: Validates the NUBAN check digit calculation and BVN formatting.
*   **[test_rules.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/tests/test_rules.py)**: Validates rule triggers and decision paths (APPROVE/BLOCKED/PENDING_OTP).

### 5. Root Project Files
*   **[antigravity.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/antigravity.py)**: Custom package replacement that renders the green/white security boot screen, loads models, and initializes the app when imported.
*   **[run.py](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/run.py)**: Convenience script to start the system using the `import antigravity` mechanic.
*   **[requirements.txt](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/requirements.txt)**: Specifies Python dependency packages (`rich`, `pandas`, `scikit-learn`, `numpy`, `pytest`, etc.).

---

## 🛡️ Key Safety Mechanics Mocked
1.  **NUBAN Integrity Verification**: Prevents transacting to invalid account numbers before contacting the NIBSS (Nigeria Inter-Bank Settlement System).
2.  **BVN Detail Audits**: Cross-checks user registration names to prevent identity theft.
3.  **USSD Shielding**: Automatically requests hardware/second-factor tokens for transaction totals exceeding `20,000 NGN` or when daily totals exceed limits on USSD channels.
4.  **AI Behavioral Isolation**: Isolates unusual user transaction amounts and locations via Isolation Forest modeling.
