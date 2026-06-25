# NairaShield AI System Operations Manual 🇳🇬🛡️
### Official User Guide & System Operation Manual

This guide describes how to operate, configure, and monitor the NairaShield Transaction Monitoring & Fraud Detection system. It covers the React Web Console, the Plotly Dash Security Center, the CLI Terminal Console, and workflow procedures for bank operators.

---

## 🔑 1. Role-Based Access Control (RBAC)

NairaShield features three distinct roles with progressive levels of clearance. Use the following default accounts to log in to the system:

| Username | Default Password | Role | Description / Permissions |
| :--- | :--- | :--- | :--- |
| **`viewer`** | `viewer123` | **Viewer** | Read-only access to transaction feeds, health status, and simulations. Cannot adjust system settings or modify alerts. |
| **`analyst`** | `analyst123` | **Analyst** | Core operator role. Can run transaction simulations, examine SHAP risk attributions, and authorize/flag/block pending high-risk alerts. |
| **`admin`** | `admin123` | **Admin** | Full system command. Can manage all analyst configurations, adjust global ML sensitivity thresholds, manually trigger drift checks, and override systems. |

---

## 💻 2. Application Interfaces

NairaShield provides three user interfaces depending on the deployment mode and the operator's operational focus:

### A. The React Web Console (Primary Operator Interface)
The React dashboard is the core workspace for risk analysts monitoring real-time queues.
*   **Access**: `http://localhost:8080` (or the configured HTTPS domain).
*   **Key Features**:
    1.  **Simulation Panel**: Input arbitrary amounts and channel types to test classifier verdicts.
    2.  **Inference Verdict Display**: Shows the classification result (**Safe / Approved** vs **Blocked / Flagged**), the exact risk probability, and local SHAP attributions.
    3.  **Recent Security Anomalies Queue**: Real-time listing of flagged transactions requiring manual review.
    4.  **Admin Sensitivity Override**: Sensitivity slider to dynamically adjust the classification threshold.

---

### B. Plotly Dash Security Hub (Deep Diagnostics & Explainability)
Used by senior risk managers to examine statistical data drift, global model behavior, and download PDF fraud intelligence summaries.
*   **Access**: `http://localhost:8060` (Launch via `python unified_dashboard.py`).
*   **Key Features**:
    1.  **Security Analytics Hub**:
        *   **Total Transactions, Fraud Interceptions, & Fraud Rate**: Live KPI metrics cards.
        *   **Incident Heatmap**: Interactive geographic map highlighting warning rates across Nigerian states (Lagos, FCT, Rivers, etc.).
        *   **30-Day Trend Charts**: Volume compared to intercepted fraud claims.
        *   **Registry Audit Logs**: Filterable, sortable, and paginated datatable of high-risk transactions.
    2.  **SHAP Model Interpreter Panel**:
        *   **Local Attribution Waterfall**: Displays the exact path the model took from the base probability to the final verdict log-odds.
        *   **Global Beeswarm Plots**: Displays feature value impact distributions for all input variables.
        *   **Dependence Plots**: Select any feature (e.g., `amount`, `channel_TRANSFER`) to display non-linear relationships with the model's output.
    3.  **PDF Report Downloader**: On-demand generation of professional, vector-styled PDF fraud reports containing model metrics, charts, and audit histories.

---

### C. The Interactive Terminal Console (CLI Mode / Developer Sandbox)
A lightweight command-line interface for terminal environments or quick diagnostics.
*   **Execution**:
    ```bash
    python run.py --demo
    ```
*   **Key Features**:
    *   Beautiful, green-and-white boot banners using the `rich` engine.
    *   Simulated live streaming transactions directly to stdout.
    *   Visual performance tables showcasing processing latency, F1-scores, and rule intercept actions.

---

## 🛠️ 3. How to Perform Key Operational Workflows

### A. Simulating a Transaction Profile
To audit a transaction signature (e.g., verifying if a customer making a `400,000 NGN` Mobile Transfer is flagged):
1.  Log in as `analyst` or `admin`.
2.  Locate the **Simulate Transaction** form on the left side of the dashboard.
3.  Enter the amount: `400000` (or slide the NGN bar).
4.  Set the **Payment Channel** to `Mobile / Wire Transfer`.
5.  Set the **Validation Registry** to `PaySim Audit Protocol`.
6.  Click **Profile Transaction**.
7.  The right panel will update with the **Inference Verdict**:
    *   If **Approved**, a green badge will appear.
    *   If **Blocked**, a red badge will display.
8.  Expand the **Local SHAP Risk Attribution** card to see the contributing features. A positive score (e.g., `channel_TRANSFER: +0.7500`) indicates that the feature pushed the transaction toward a fraud classification.

---

### B. Resolving Security Alerts (Analyst Queue)
When transactions are flagged as high risk (exceeding the sensitivity threshold), they appear in the **Recent Security Anomalies** panel at the bottom of the dashboard.

1.  Review the alert parameters: **Alert ID**, **Channel**, **Amount**, **Location**, and **Timestamp**.
2.  If the transaction has a high-risk rating (indicated by a red warning box), the analyst should take action:
    *   **Request OTP**: Routes a 2FA challenge via SMS/Email to the cardholder, changing the status to `PENDING_OTP` until confirmation.
    *   **Block / Deny**: Manually overrides the transaction, blocking fund movement, changing status to `BLOCKED`.
3.  The audit actions, including the operator's username and timestamp, are instantly saved to the database.

---

### C. Tuning Classifier Sensitivity (Admin Overrides)
If the model is flagging too many legitimate transactions (false positives), or missing suspect transactions (false negatives), an administrator can adjust the threshold:

1.  Log in as `admin`.
2.  Scroll to the **Global Sensitivity Overrides** panel.
3.  Adjust the **Model Fraud Threshold** slider:
    *   **Raise the Threshold** (e.g., to `0.80`): Makes the model less sensitive, reducing false positives but potentially letting higher-risk transactions pass.
    *   **Lower the Threshold** (e.g., to `0.35`): Makes the model highly sensitive, catching more fraud but increasing the frequency of false alarms/OTP requests.
4.  Click **Apply**. The cutoff propagates immediately to all active scoring pipelines.

---

### D. Exporting Fraud Intelligence Reports
To generate executive reports for audit committees or security officers:

1.  Open the **Plotly Dash Dashboard** (`http://localhost:8060`).
2.  Click **Download Fraud Intelligence Report (PDF)** in the header.
3.  The backend compiles live data, including metrics, active alert registries, and SHAP diagrams, into a file styled with Nigerian banking theme colors (Emerald & Navy).
4.  Save the downloaded PDF.

---

## 📈 4. Data Drift & Retraining Checks
The drift monitoring daemon runs in the background. It analyzes transaction distributions over time to prevent model degradation:
*   **PSI Thresholds**: Checks if the Population Stability Index for feature ranges (like transaction amount) deviates beyond `0.2`.
*   **Retraining Trigger**: If the evaluated F1-score falls below `0.85`, it automatically initiates preprocessing and SMOTE resampling on fresh database entries, builds a new tuned XGBoost classifier, backs up the old model, and swaps the active weights.
*   **Retraining Logs**: Open the file [drift_monitor.log](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/drift_monitor.log) or query [drift_monitor.db](file:///c:/Users/Tommy/OneDrive/Documents/Benjamin/drift_monitor.db) (SQLite) to audit retraining logs.
