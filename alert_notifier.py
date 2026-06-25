"""
NairaShield Alert Notifier Module.

Sends multi-channel alerts (Email via SMTP + SMS via Termii or Twilio) whenever
a transaction is flagged as fraudulent with confidence above the configured
threshold (default 85%).

Each alert includes:
  - Transaction ID, amount, timestamp, channel, location
  - Model fraud probability & rules triggered
  - Top 3 SHAP feature contributions (risk reasons)

Usage:
    from alert_notifier import AlertNotifier
    notifier = AlertNotifier()
    notifier.dispatch(alert_payload)

Environment Variables (copy .env.example to .env and fill in credentials):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    ALERT_FROM_EMAIL, ALERT_TO_EMAILS (comma-separated)
    TERMII_API_KEY, TERMII_SENDER_ID, TERMII_RECIPIENTS
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_TO_NUMBERS
    SMS_PROVIDER (termii | twilio)
    ALERT_CONFIDENCE_THRESHOLD (float, default 0.85)
"""

import os
import json
import smtplib
import logging
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

# Try loading .env automatically if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Credentials must be set as real environment variables

# Optional HTTP library for Termii/Twilio REST calls
try:
    import urllib.request
    import urllib.parse
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

# --- Logger ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("NairaShield.Notifier")


# =====================================================================
# SHAP FORMATTER UTILITY
# =====================================================================

def format_top_shap_reasons(shap_values: dict, top_n: int = 3) -> list[dict]:
    """
    Given a dict of {feature_name: shap_value}, returns the top_n features
    sorted by absolute SHAP impact, formatted for alert messages.
    """
    if not shap_values:
        return []

    sorted_features = sorted(
        shap_values.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )[:top_n]

    reasons = []
    for feat, val in sorted_features:
        direction = "INCREASES" if val > 0 else "DECREASES"
        clean_name = (
            feat.replace("channel_", "Channel: ")
                .replace("source_dataset_", "Pipeline: ")
        )
        reasons.append({
            "feature": clean_name,
            "shap_value": round(val, 4),
            "direction": direction,
            "impact_pct": f"{abs(val) * 100:.2f}%"
        })
    return reasons


# =====================================================================
# MESSAGE FORMATTERS
# =====================================================================

def build_email_html(alert: dict) -> tuple[str, str]:
    """
    Builds a rich HTML email body and plain-text fallback for a fraud alert.
    Returns (subject, html_body).
    """
    tx_id       = alert.get("transaction_id", "N/A")
    alert_id    = alert.get("alert_id", "N/A")
    amount      = alert.get("amount", 0.0)
    channel     = alert.get("channel", "N/A")
    location    = alert.get("location", "N/A")
    timestamp   = alert.get("timestamp", datetime.now().isoformat())
    model_prob  = alert.get("model_probability", 0.0)
    rule_score  = alert.get("rule_risk_score", 0.0)
    rules       = alert.get("triggered_rules", [])
    shap_vals   = alert.get("shap_values", {})
    top_reasons = format_top_shap_reasons(shap_vals, top_n=3)

    confidence  = max(model_prob, rule_score) * 100
    subject     = f"[NairaShield CRITICAL] Fraud Alert {alert_id} | Tx {tx_id} | NGN {amount:,.2f}"

    # Build SHAP rows
    shap_rows = ""
    if top_reasons:
        for i, r in enumerate(top_reasons, 1):
            arrow = "&#x2B06;" if r["direction"] == "INCREASES" else "&#x2B07;"
            color = "#ef4444" if r["direction"] == "INCREASES" else "#10b981"
            shap_rows += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #1f2937;font-weight:600;">{i}.</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1f2937;">{r['feature']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1f2937;color:{color};font-family:monospace;font-weight:700;">
                  {arrow} {r['shap_value']:+.4f} ({r['impact_pct']})
              </td>
              <td style="padding:8px 12px;border-bottom:1px solid #1f2937;color:{color};">{r['direction']} risk</td>
            </tr>"""
    else:
        shap_rows = '<tr><td colspan="4" style="padding:8px 12px;color:#9ca3af;text-align:center;">SHAP values not available for this alert</td></tr>'

    rules_text = ", ".join(rules) if rules else "None triggered"

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>NairaShield Fraud Alert</title>
</head>
<body style="margin:0;padding:0;background-color:#0b0f19;font-family:'Segoe UI',Arial,sans-serif;color:#f3f4f6;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;margin:0 auto;padding:32px 16px;">
    <tr>
      <td>
        <!-- Header -->
        <div style="background:linear-gradient(135deg,#0b0f19 0%,#111827 100%);border:1px solid rgba(239,68,68,0.4);border-radius:16px;padding:24px 32px;margin-bottom:24px;text-align:center;">
          <p style="margin:0 0 4px 0;font-size:12px;letter-spacing:0.2em;color:#9ca3af;text-transform:uppercase;">NairaShield AI Security</p>
          <h1 style="margin:0;font-size:26px;font-weight:800;background:linear-gradient(135deg,#ef4444,#f97316);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            &#x26A0; FRAUD ALERT DETECTED
          </h1>
          <div style="display:inline-block;margin-top:12px;padding:6px 20px;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);border-radius:100px;font-size:22px;font-weight:900;color:#ef4444;letter-spacing:0.05em;">
            {confidence:.1f}% CONFIDENCE
          </div>
        </div>

        <!-- Transaction Summary -->
        <div style="background:rgba(17,24,39,0.9);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:24px 32px;margin-bottom:20px;">
          <h2 style="margin:0 0 16px 0;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#10b981;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:12px;">
            Transaction Summary
          </h2>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td width="50%" style="padding:6px 0;">
                <span style="color:#9ca3af;font-size:12px;">Alert ID</span><br>
                <span style="font-family:monospace;font-weight:700;font-size:15px;color:#f97316;">{alert_id}</span>
              </td>
              <td width="50%" style="padding:6px 0;">
                <span style="color:#9ca3af;font-size:12px;">Transaction ID</span><br>
                <span style="font-family:monospace;font-weight:700;font-size:15px;color:#f3f4f6;">{tx_id}</span>
              </td>
            </tr>
            <tr>
              <td width="50%" style="padding:10px 0 6px;">
                <span style="color:#9ca3af;font-size:12px;">Amount</span><br>
                <span style="font-size:22px;font-weight:900;color:#ef4444;">&#8358;{amount:,.2f}</span>
              </td>
              <td width="50%" style="padding:10px 0 6px;">
                <span style="color:#9ca3af;font-size:12px;">Timestamp</span><br>
                <span style="font-weight:600;font-size:14px;color:#f3f4f6;">{timestamp[:19].replace("T"," ")}</span>
              </td>
            </tr>
            <tr>
              <td width="50%" style="padding:6px 0;">
                <span style="color:#9ca3af;font-size:12px;">Channel</span><br>
                <span style="font-weight:600;color:#3b82f6;">{channel}</span>
              </td>
              <td width="50%" style="padding:6px 0;">
                <span style="color:#9ca3af;font-size:12px;">Location</span><br>
                <span style="font-weight:600;color:#f3f4f6;">{location}</span>
              </td>
            </tr>
            <tr>
              <td width="50%" style="padding:6px 0;">
                <span style="color:#9ca3af;font-size:12px;">Model Probability</span><br>
                <span style="font-weight:700;color:#ef4444;">{model_prob*100:.1f}%</span>
              </td>
              <td width="50%" style="padding:6px 0;">
                <span style="color:#9ca3af;font-size:12px;">Rules Risk Score</span><br>
                <span style="font-weight:700;color:#f59e0b;">{rule_score*100:.1f}%</span>
              </td>
            </tr>
            <tr>
              <td colspan="2" style="padding:8px 0 0;">
                <span style="color:#9ca3af;font-size:12px;">Rules Triggered</span><br>
                <span style="font-family:monospace;font-size:13px;color:#a78bfa;">{rules_text}</span>
              </td>
            </tr>
          </table>
        </div>

        <!-- Top 3 SHAP Reasons -->
        <div style="background:rgba(17,24,39,0.9);border:1px solid rgba(167,139,250,0.2);border-radius:12px;padding:24px 32px;margin-bottom:20px;">
          <h2 style="margin:0 0 16px 0;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#a78bfa;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:12px;">
            Top 3 SHAP Risk Explanations
          </h2>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <thead>
              <tr style="background:rgba(167,139,250,0.1);">
                <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;">#</th>
                <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;">Feature</th>
                <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;">SHAP Value</th>
                <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;">Effect</th>
              </tr>
            </thead>
            <tbody style="color:#f3f4f6;">{shap_rows}</tbody>
          </table>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:16px;color:#4b5563;font-size:12px;">
          <p style="margin:0;">This is an automated security notification from <strong style="color:#10b981;">NairaShield AI</strong>.</p>
          <p style="margin:4px 0 0;">Do not reply to this email. Contact your system administrator if this alert is incorrect.</p>
        </div>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return subject, html_body


def build_sms_text(alert: dict) -> str:
    """
    Builds a concise SMS message for a fraud alert (max ~160 chars per segment).
    """
    tx_id      = alert.get("transaction_id", "N/A")
    amount     = alert.get("amount", 0.0)
    channel    = alert.get("channel", "N/A")
    location   = alert.get("location", "N/A")
    timestamp  = alert.get("timestamp", datetime.now().isoformat())[:16].replace("T", " ")
    model_prob = alert.get("model_probability", 0.0)
    rule_score = alert.get("rule_risk_score", 0.0)
    shap_vals  = alert.get("shap_values", {})
    rules      = alert.get("triggered_rules", [])
    top_reasons = format_top_shap_reasons(shap_vals, top_n=3)

    confidence = max(model_prob, rule_score) * 100

    # Top SHAP reasons as short bullets
    reason_lines = []
    for i, r in enumerate(top_reasons, 1):
        sign = "+" if r["direction"] == "INCREASES" else "-"
        reason_lines.append(f"  {i}. {r['feature']} ({sign}{abs(r['shap_value']):.3f})")

    reasons_text = "\n".join(reason_lines) if reason_lines else "  N/A"

    # Include triggered rules if present and no SHAP
    if not reason_lines and rules:
        reasons_text = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(rules[:3]))

    msg = (
        f"[NairaShield] FRAUD ALERT\n"
        f"Tx: {tx_id}\n"
        f"Amount: NGN {amount:,.0f}\n"
        f"Channel: {channel} | {location}\n"
        f"Time: {timestamp}\n"
        f"Confidence: {confidence:.1f}%\n"
        f"Top Risk Factors:\n{reasons_text}\n"
        f"-- Auto-blocked by NairaShield AI --"
    )
    return msg


# =====================================================================
# DELIVERY ENGINES
# =====================================================================

class EmailSender:
    """Sends HTML fraud alert emails via SMTP."""

    def __init__(self):
        self.host     = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port     = int(os.getenv("SMTP_PORT", "587"))
        self.user     = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASS", "")
        self.from_addr = os.getenv("ALERT_FROM_EMAIL", self.user)
        recipients_raw = os.getenv("ALERT_TO_EMAILS", "")
        self.recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    def is_configured(self) -> bool:
        return bool(self.user and self.password and self.recipients)

    def send(self, alert: dict) -> bool:
        if not self.is_configured():
            log.warning("[Email] Not configured — skipping. Set SMTP_USER, SMTP_PASS, ALERT_TO_EMAILS in .env")
            return False
        try:
            subject, html_body = build_email_html(alert)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.from_addr
            msg["To"]      = ", ".join(self.recipients)

            # Plain-text fallback
            plain_text = (
                f"NairaShield FRAUD ALERT\n"
                f"Alert ID: {alert.get('alert_id','N/A')}\n"
                f"Tx ID: {alert.get('transaction_id','N/A')}\n"
                f"Amount: NGN {alert.get('amount',0):,.2f}\n"
                f"Timestamp: {alert.get('timestamp','')[:19]}\n"
                f"Confidence: {max(alert.get('model_probability',0), alert.get('rule_risk_score',0))*100:.1f}%\n"
            )
            msg.attach(MIMEText(plain_text, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.from_addr, self.recipients, msg.as_string())

            log.info(f"[Email] Alert dispatched to: {self.recipients}")
            return True
        except Exception as e:
            log.error(f"[Email] Delivery failed: {e}")
            return False


class TermiiSMSSender:
    """Sends SMS alerts via Termii API (recommended for Nigerian numbers)."""

    API_URL = "https://api.ng.termii.com/api/sms/send"

    def __init__(self):
        self.api_key    = os.getenv("TERMII_API_KEY", "")
        self.sender_id  = os.getenv("TERMII_SENDER_ID", "NairaShield")
        recipients_raw  = os.getenv("TERMII_RECIPIENTS", "")
        self.recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    def is_configured(self) -> bool:
        return bool(self.api_key and self.recipients)

    def _post_json(self, url: str, payload: dict) -> dict:
        """Pure-stdlib HTTP POST with JSON body."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def send(self, alert: dict) -> bool:
        if not self.is_configured():
            log.warning("[Termii] Not configured — skipping. Set TERMII_API_KEY and TERMII_RECIPIENTS in .env")
            return False
        sms_text = build_sms_text(alert)
        all_ok = True
        for phone in self.recipients:
            try:
                payload = {
                    "to":        phone,
                    "from":      self.sender_id,
                    "sms":       sms_text,
                    "type":      "plain",
                    "api_key":   self.api_key,
                    "channel":   "generic"
                }
                result = self._post_json(self.API_URL, payload)
                log.info(f"[Termii] SMS sent to {phone}: {result.get('message','ok')}")
            except Exception as e:
                log.error(f"[Termii] SMS delivery failed to {phone}: {e}")
                all_ok = False
        return all_ok


class TwilioSMSSender:
    """Sends SMS alerts via Twilio REST API (international fallback)."""

    def __init__(self):
        self.account_sid  = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token   = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number  = os.getenv("TWILIO_FROM_NUMBER", "")
        recipients_raw    = os.getenv("TWILIO_TO_NUMBERS", "")
        self.recipients   = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number and self.recipients)

    def _post_form(self, url: str, payload: dict, auth: tuple) -> dict:
        """Pure-stdlib HTTP POST with form-encoded body and Basic Auth."""
        import base64
        data = urllib.parse.urlencode(payload).encode("utf-8")
        credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {credentials}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def send(self, alert: dict) -> bool:
        if not self.is_configured():
            log.warning("[Twilio] Not configured — skipping. Set TWILIO_* vars in .env")
            return False
        sms_text = build_sms_text(alert)
        all_ok = True
        for phone in self.recipients:
            try:
                url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
                payload = {
                    "Body": sms_text,
                    "From": self.from_number,
                    "To":   phone
                }
                result = self._post_form(url, payload, (self.account_sid, self.auth_token))
                log.info(f"[Twilio] SMS sent to {phone}: SID={result.get('sid','N/A')}")
            except Exception as e:
                log.error(f"[Twilio] SMS delivery failed to {phone}: {e}")
                all_ok = False
        return all_ok


# =====================================================================
# MAIN DISPATCHER
# =====================================================================

class AlertNotifier:
    """
    Central alert dispatcher for the NairaShield fraud alerting system.
    Reads provider config from environment variables and dispatches
    email + SMS simultaneously when an alert crosses the confidence threshold.
    """

    def __init__(self):
        self.threshold  = float(os.getenv("ALERT_CONFIDENCE_THRESHOLD", "0.85"))
        self.sms_provider = os.getenv("SMS_PROVIDER", "termii").lower()

        self.email_sender = EmailSender()
        self.sms_sender   = TermiiSMSSender() if self.sms_provider == "termii" else TwilioSMSSender()

        log.info(
            f"[Notifier] Initialized — threshold={self.threshold*100:.0f}% | "
            f"SMS={self.sms_provider} | "
            f"Email={'configured' if self.email_sender.is_configured() else 'NOT configured'} | "
            f"SMS={'configured' if self.sms_sender.is_configured() else 'NOT configured'}"
        )

    def should_alert(self, alert: dict) -> bool:
        """Returns True if the alert confidence exceeds the dispatch threshold."""
        confidence = max(
            alert.get("model_probability", 0.0),
            alert.get("rule_risk_score", 0.0)
        )
        return confidence >= self.threshold

    def dispatch(self, alert: dict) -> dict:
        """
        Evaluates whether an alert crosses the notification threshold.
        If yes, dispatches Email and SMS and returns a delivery report.

        Args:
            alert: dict with keys:
                alert_id, transaction_id, amount, channel, location,
                timestamp, model_probability, rule_risk_score,
                triggered_rules, shap_values (optional)

        Returns:
            dict with keys: threshold_met, confidence, email_sent, sms_sent
        """
        confidence = max(
            alert.get("model_probability", 0.0),
            alert.get("rule_risk_score", 0.0)
        )

        if not self.should_alert(alert):
            log.info(
                f"[Notifier] Alert {alert.get('alert_id','?')} below threshold "
                f"({confidence*100:.1f}% < {self.threshold*100:.0f}%) — skipping notifications."
            )
            return {
                "threshold_met": False,
                "confidence": confidence,
                "email_sent": False,
                "sms_sent": False
            }

        log.warning(
            f"[Notifier] HIGH-CONFIDENCE FRAUD: {alert.get('alert_id','?')} "
            f"Tx={alert.get('transaction_id','?')} "
            f"Amount=NGN {alert.get('amount',0):,.0f} "
            f"Confidence={confidence*100:.1f}% — dispatching alerts..."
        )

        email_ok = self.email_sender.send(alert)
        sms_ok   = self.sms_sender.send(alert)

        return {
            "threshold_met": True,
            "confidence": confidence,
            "email_sent": email_ok,
            "sms_sent": sms_ok
        }


# =====================================================================
# STANDALONE TEST / DEMO MODE
# =====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print(" NairaShield Alert Notifier — Dry-Run Demo")
    print("=" * 60)
    print()

    # Simulate a high-confidence fraud alert with SHAP values
    mock_alert = {
        "alert_id": "ALT-DEMO-001",
        "transaction_id": "TXN-200099",
        "amount": 2_450_000.00,
        "channel": "TRANSFER",
        "location": "Lagos",
        "timestamp": datetime.now().isoformat(),
        "model_probability": 0.9933,
        "rule_risk_score": 0.85,
        "triggered_rules": ["USSD_SINGLE_LIMIT_EXCEEDED", "NIGHT_LARGE_TRANSFER"],
        "shap_values": {
            "amount": 1.8420,
            "channel_TRANSFER": 0.7510,
            "source_dataset_PaySim": 0.3940,
            "channel_CASH_OUT": -0.2010,
            "channel_DEBIT": -0.4500,
            "channel_CARD_WEB": 0.1120,
            "source_dataset_IEEE-CIS": -0.0800,
            "channel_CARD_HOST": 0.0050,
            "channel_CARD_PHONE": 0.0010,
            "channel_CARD_RECURRING": 0.0020,
            "channel_CARD_STORE": 0.0030,
            "channel_CASH_IN": -0.0040,
            "channel_PAYMENT": 0.0010,
        }
    }

    print(f"Mock alert payload:")
    print(f"  Transaction ID : {mock_alert['transaction_id']}")
    print(f"  Amount         : NGN {mock_alert['amount']:,.2f}")
    print(f"  Confidence     : {max(mock_alert['model_probability'], mock_alert['rule_risk_score'])*100:.1f}%")
    print(f"  Rules triggered: {mock_alert['triggered_rules']}")
    print()

    top3 = format_top_shap_reasons(mock_alert["shap_values"], top_n=3)
    print("Top 3 SHAP Risk Reasons:")
    for i, r in enumerate(top3, 1):
        sign = "+" if r["direction"] == "INCREASES" else "-"
        print(f"  {i}. {r['feature']}: {sign}{abs(r['shap_value']):.4f} — {r['direction']} fraud risk by {r['impact_pct']}")
    print()

    print("SMS preview:")
    print("-" * 50)
    print(build_sms_text(mock_alert))
    print("-" * 50)
    print()

    notifier = AlertNotifier()
    result   = notifier.dispatch(mock_alert)

    print()
    print("Dispatch result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print()
    print("NOTE: Set credentials in .env file to send live notifications.")
