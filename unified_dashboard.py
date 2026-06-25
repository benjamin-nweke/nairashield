"""
NairaShield Unified Portal: Real-Time Fraud Analytics & SHAP Interpretability Dashboard.
Built using Plotly Dash.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib
import shap
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# PDF Report Generator (optional — requires reportlab)
try:
    from report_generator import generate_report, DEFAULT_MODEL_METRICS, DEFAULT_FRAUD_PATTERNS, DEFAULT_SHAP_IMPORTANCE
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# =====================================================================
# DATA & MODEL INITIALIZATION
# =====================================================================

MODEL_PATH = "xgboost_model_tuned.joblib"
DATA_PATH = "test.csv"
ALERTS_PATH = "alerts_log.json"

# Load ML model
model = None
X_test = None
explainer = None
shap_values = None
top_5_features = []

if os.path.exists(MODEL_PATH) and os.path.exists(DATA_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        df_test = pd.read_csv(DATA_PATH)
        X_test = df_test.drop(columns=["is_fraud"])
        
        # Initialize Explainer
        explainer = shap.TreeExplainer(model)
        shap_values = explainer(X_test)
        
        # Calculate top features by mean absolute SHAP
        mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
        sorted_idx = np.argsort(mean_abs_shap)[::-1]
        top_5_features = list(X_test.columns[sorted_idx[:5]])
        print(f"[OK] SHAP explainer initialized. Top features: {top_5_features}")
    except Exception as e:
        print(f"[Error] Failed to initialize SHAP components: {e}")
else:
    print("[Warning] Missing model or test dataset. SHAP tab will run in demo/fallback mode.")

# 13 Standard features template
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

# =====================================================================
# SEEDING ANALYTICS & HISTORICAL ALERTS DATA
# =====================================================================

def load_alerts_and_metrics():
    # Base metrics
    total_tx_today = 3420
    flagged_today = 64
    
    # Load live alerts from alerts_log.json if exists
    live_alerts = []
    if os.path.exists(ALERTS_PATH):
        try:
            with open(ALERTS_PATH, "r") as f:
                live_alerts = json.load(f)
            # Add live count to today's summary
            flagged_today += len(live_alerts)
            total_tx_today += len(live_alerts) * 45 # Assuming 45x benign ratio
        except Exception as e:
            print(f"[Warning] Failed to read alerts log: {e}")
            
    fraud_rate_today = (flagged_today / total_tx_today) * 100
    
    # Seeding historical table records
    historical_records = [
        {"alert_id": "ALT882711", "transaction_id": "TXN100201", "amount": 420000.0, "channel": "TRANSFER", "location": "Lagos", "risk_score": 0.94, "status": "BLOCKED", "timestamp": "2026-06-23T08:14:22"},
        {"alert_id": "ALT192837", "transaction_id": "TXN100205", "amount": 890000.0, "channel": "TRANSFER", "location": "Port Harcourt", "risk_score": 0.88, "status": "PENDING_OTP", "timestamp": "2026-06-23T09:33:11"},
        {"alert_id": "ALT662719", "transaction_id": "TXN100222", "amount": 1500000.0, "channel": "USSD", "location": "Lagos", "risk_score": 0.98, "status": "BLOCKED", "timestamp": "2026-06-23T11:05:43"},
        {"alert_id": "ALT891029", "transaction_id": "TXN100259", "amount": 620000.0, "channel": "CARD_WEB", "location": "Abuja", "risk_score": 0.72, "status": "PENDING_OTP", "timestamp": "2026-06-23T12:45:19"},
        {"alert_id": "ALT447382", "transaction_id": "TXN100270", "amount": 75000.0, "channel": "USSD", "location": "Kano", "risk_score": 0.86, "status": "BLOCKED", "timestamp": "2026-06-23T14:12:05"},
        {"alert_id": "ALT338192", "transaction_id": "TXN100288", "amount": 2500000.0, "channel": "TRANSFER", "location": "Benin City", "risk_score": 0.99, "status": "BLOCKED", "timestamp": "2026-06-23T15:55:34"},
        {"alert_id": "ALT559102", "transaction_id": "TXN100311", "amount": 120000.0, "channel": "CARD_WEB", "location": "Ibadan", "risk_score": 0.65, "status": "PENDING_OTP", "timestamp": "2026-06-23T17:22:47"}
    ]
    
    # Merge live alerts into records
    merged_table_data = []
    for alert in live_alerts:
        merged_table_data.append({
            "alert_id": alert.get("alert_id", "N/A"),
            "transaction_id": alert.get("transaction_id", "N/A"),
            "amount": alert.get("amount", 0.0),
            "channel": alert.get("channel", "N/A"),
            "location": alert.get("location", "N/A"),
            # map scores
            "risk_score": float(max(alert.get("model_probability", 0.0), alert.get("rule_risk_score", 0.0))),
            "status": "BLOCKED" if max(alert.get("model_probability", 0.0), alert.get("rule_risk_score", 0.0)) >= 0.80 else "PENDING_OTP",
            "timestamp": alert.get("timestamp", "")[:19] # trim microseconds
        })
        
    merged_table_data.extend(historical_records)
    
    # Sort merged list by timestamp descending
    merged_table_data.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return total_tx_today, flagged_today, fraud_rate_today, merged_table_data

total_tx, flagged_count, fraud_rate, table_data = load_alerts_and_metrics()

# =====================================================================
# GEOGRAPHIC GEOLOCATION COORDINATES (NIGERIA CAPITALS)
# =====================================================================

nigeria_states_data = pd.DataFrame([
    {"state": "Lagos", "lat": 6.5244, "lon": 3.3792, "fraud_count": 142, "amount_ngn": 18250000.0},
    {"state": "Abuja (FCT)", "lat": 9.0765, "lon": 7.3986, "fraud_count": 67, "amount_ngn": 9430000.0},
    {"state": "Port Harcourt (Rivers)", "lat": 4.8156, "lon": 7.0498, "fraud_count": 58, "amount_ngn": 6800000.0},
    {"state": "Kano", "lat": 12.0022, "lon": 8.5919, "fraud_count": 34, "amount_ngn": 3200000.0},
    {"state": "Ibadan (Oyo)", "lat": 7.3775, "lon": 3.9470, "fraud_count": 41, "amount_ngn": 4850000.0},
    {"state": "Kaduna", "lat": 10.5105, "lon": 7.4165, "fraud_count": 23, "amount_ngn": 2100000.0},
    {"state": "Benin City (Edo)", "lat": 6.3350, "lon": 5.6263, "fraud_count": 31, "amount_ngn": 3950000.0},
    {"state": "Abeokuta (Ogun)", "lat": 7.1599, "lon": 3.3486, "fraud_count": 28, "amount_ngn": 2400000.0},
    {"state": "Enugu", "lat": 6.4584, "lon": 7.5083, "fraud_count": 19, "amount_ngn": 1750000.0},
    {"state": "Warri (Delta)", "lat": 5.5174, "lon": 5.7508, "fraud_count": 25, "amount_ngn": 3100000.0},
    {"state": "Jos (Plateau)", "lat": 9.8965, "lon": 8.8583, "fraud_count": 12, "amount_ngn": 950000.0},
    {"state": "Maiduguri (Borno)", "lat": 11.8311, "lon": 13.1509, "fraud_count": 8, "amount_ngn": 620000.0}
])

# =====================================================================
# DASHBOARD GRAPH GENERATOR UTILITIES (ANALYTICS HUB)
# =====================================================================

def make_fraud_trend_chart():
    np.random.seed(42)
    dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)][::-1]
    
    # Generate realistic values
    total_volumes = [int(np.random.randint(4200, 5600)) for _ in range(30)]
    fraud_counts = [int(np.random.randint(45, 95)) for _ in range(30)]
    
    fig = go.Figure()
    # Daily total volume trace (Secondary axis)
    fig.add_trace(go.Scatter(
        x=dates,
        y=total_volumes,
        name="Total Transactions",
        line=dict(color="rgba(59, 130, 246, 0.4)", width=2),
        fill="tozeroy",
        fillcolor="rgba(59, 130, 246, 0.05)",
        yaxis="y2"
    ))
    
    # Flagged fraud trace
    fig.add_trace(go.Scatter(
        x=dates,
        y=fraud_counts,
        name="Flagged Fraud Claims",
        line=dict(color="#ef4444", width=3),
        marker=dict(size=6, color="#ef4444")
    ))
    
    fig.update_layout(
        title="30-Day Fraud Incident and Transaction Volume Trend",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f3f4f6', family='Outfit, sans-serif'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', showticklabels=True),
        yaxis=dict(
            title=dict(text="Flagged Fraud Volume", font=dict(color="#ef4444")),
            tickfont=dict(color="#ef4444"),
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)'
        ),
        yaxis2=dict(
            title=dict(text="Total Transaction Count", font=dict(color="rgb(59, 130, 246)")),
            tickfont=dict(color="rgb(59, 130, 246)"),
            overlaying="y",
            side="right",
            gridcolor='rgba(0,0,0,0)'
        ),
        margin=dict(l=50, r=50, t=60, b=40),
        height=320
    )
    return fig

def make_nigerian_heatmap():
    # Draw scattergeo focused on Nigeria Capital capitals
    fig = go.Figure()
    
    hover_text = nigeria_states_data.apply(
        lambda r: f"State: {r['state']}<br>Fraud Incidents: {r['fraud_count']}<br>Loss Intercepted: ₦{r['amount_ngn']:,.2f}",
        axis=1
    )
    
    fig.add_trace(go.Scattergeo(
        lon=nigeria_states_data["lon"],
        lat=nigeria_states_data["lat"],
        text=hover_text,
        hoverinfo="text",
        marker=dict(
            size=nigeria_states_data["fraud_count"] * 0.25 + 10,
            color=nigeria_states_data["fraud_count"],
            colorscale="Reds",
            showscale=True,
            colorbar=dict(
                title=dict(text="Fraud Flags", side="top"),
                len=0.7,
                thickness=15
            ),
            line=dict(color="#0b0f19", width=1),
            opacity=0.9
        )
    ))
    
    fig.update_geos(
        projection_type="mercator",
        showcountries=True,
        countrycolor="rgba(16, 185, 129, 0.4)",
        showland=True,
        landcolor="#111827",
        showocean=True,
        oceancolor="#0b0f19",
        showframe=False,
        lonaxis=dict(range=[2.2, 14.8]), # boundaries of Nigeria
        lataxis=dict(range=[4.0, 14.0])
    )
    
    fig.update_layout(
        title="Geographic Heatmap: Security Incidents by Nigerian State",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f3f4f6', family='Outfit, sans-serif'),
        margin=dict(l=10, r=10, t=50, b=10),
        height=320
    )
    return fig

def make_merchant_chart():
    merchants_df = pd.DataFrame([
        {"merchant": "Flutterwave Checkout", "flags": 84},
        {"merchant": "OPay Agent Network", "flags": 73},
        {"merchant": "Bet9ja Wallet", "flags": 62},
        {"merchant": "Jumia Pay Portal", "flags": 41},
        {"merchant": "Konga Web Checkout", "flags": 29},
        {"merchant": "Palmpay POS Point", "flags": 25}
    ]).sort_values(by="flags", ascending=True)
    
    fig = px.bar(
        merchants_df,
        x="flags",
        y="merchant",
        orientation="h",
        color="flags",
        color_continuous_scale="Reds",
        labels={"flags": "Interception Warnings", "merchant": "Merchant Registry"}
    )
    
    fig.update_layout(
        title="Top Flagged Merchants (Aggregated Alerts)",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        coloraxis_showscale=False,
        font=dict(color='#f3f4f6', family='Outfit, sans-serif'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', zerolinecolor='rgba(255,255,255,0.1)'),
        yaxis=dict(gridcolor='rgba(0,0,0,0)'),
        margin=dict(l=150, r=20, t=50, b=40),
        height=280
    )
    return fig

# =====================================================================
# SHAP CHART GENERATORS (PORTED FROM SHAP_DASHBOARD)
# =====================================================================

def make_importance_bar_chart():
    if shap_values is None or X_test is None:
        return go.Figure()
    
    mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
    importance_df = pd.DataFrame({
        "Feature": X_test.columns,
        "Importance": mean_abs_shap
    }).sort_values(by="Importance", ascending=True)
    
    importance_df["Display Name"] = importance_df["Feature"].apply(
        lambda x: x.replace("channel_", "Channel: ").replace("source_dataset_", "Pipeline: ")
    )
    
    fig = px.bar(
        importance_df,
        x="Importance",
        y="Display Name",
        orientation="h",
        color="Importance",
        color_continuous_scale="Viridis",
        labels={"Importance": "Mean |SHAP Value| (Average Risk Impact)"}
    )
    
    fig.update_layout(
        title="Global Feature Importance (Average Magnitude of SHAP Values)",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f3f4f6', family='Outfit, sans-serif'),
        coloraxis_showscale=False,
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', zerolinecolor='rgba(255,255,255,0.1)'),
        yaxis=dict(gridcolor='rgba(0,0,0,0)', tickfont=dict(size=11)),
        margin=dict(l=150, r=20, t=50, b=50),
        height=450
    )
    return fig

def make_beeswarm_plot():
    if shap_values is None or X_test is None:
        return go.Figure()
    
    shap_vals = shap_values.values
    mean_abs_shap = np.abs(shap_vals).mean(axis=0)
    sorted_idx = np.argsort(mean_abs_shap)
    
    features_sorted = X_test.columns[sorted_idx]
    
    plot_x = []
    plot_y = []
    plot_color = []
    plot_hover = []
    
    np.random.seed(42)
    sample_size = min(len(X_test), 250)
    indices = np.random.choice(len(X_test), size=sample_size, replace=False)
    
    for y_val, feat_idx in enumerate(sorted_idx):
        feat_name = X_test.columns[feat_idx]
        display_name = feat_name.replace("channel_", "").replace("source_dataset_", "")
        
        vals = X_test.iloc[indices, feat_idx].values
        shaps = shap_vals[indices, feat_idx]
        
        jitter = np.random.uniform(-0.25, 0.25, size=sample_size)
        
        for val, shap_val, jit in zip(vals, shaps, jitter):
            plot_x.append(shap_val)
            plot_y.append(y_val + jit)
            plot_color.append(val)
            plot_hover.append(
                f"Feature: {display_name}<br>"
                f"Feature Value: {val:.4f}<br>"
                f"SHAP Value: {shap_val:.4f} (Log-Odds Impact)"
            )
            
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_x,
        y=plot_y,
        mode='markers',
        marker=dict(
            size=6,
            color=plot_color,
            colorscale='RdBu_r',
            colorbar=dict(
                title=dict(text="Feature Value", side="top"),
                tickmode="array",
                tickvals=[0, 1],
                ticktext=["Low (0)", "High (1)"],
                len=0.6,
                thickness=15
            ),
            showscale=True,
            opacity=0.75
        ),
        text=plot_hover,
        hoverinfo='text'
    ))
    
    fig.update_layout(
        title="SHAP Beeswarm Plot (Feature Value Impact Distribution)",
        xaxis_title="SHAP Value (Impact on Fraud Probability)",
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(features_sorted))),
            ticktext=[f.replace("channel_", "Channel: ").replace("source_dataset_", "Pipeline: ") for f in features_sorted],
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)'
        ),
        xaxis=dict(
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)'
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f3f4f6', family='Outfit, sans-serif'),
        margin=dict(l=150, r=20, t=50, b=50),
        height=450
    )
    return fig

def make_dependence_plot(feature_name):
    if shap_values is None or X_test is None:
        return go.Figure()
    
    x_data = X_test[feature_name].values
    y_data = shap_values[:, feature_name].values
    
    clean_title = feature_name.replace("channel_", "Channel: ").replace("source_dataset_", "Pipeline: ")
    
    fig = px.scatter(
        x=x_data,
        y=y_data,
        color=x_data,
        color_continuous_scale="RdBu_r",
        labels={"x": f"Feature Value ({clean_title})", "y": "SHAP Value (Risk Output Impact)"}
    )
    
    fig.update_traces(marker=dict(size=8, opacity=0.8))
    fig.update_layout(
        title=f"SHAP Dependence Plot: {clean_title}",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        coloraxis_showscale=False,
        font=dict(color='#f3f4f6', family='Outfit, sans-serif'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', zerolinecolor='rgba(255,255,255,0.1)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', zerolinecolor='rgba(255,255,255,0.1)'),
        margin=dict(l=60, r=20, t=50, b=50),
        height=400
    )
    return fig

# =====================================================================
# DASH APP CREATION
# =====================================================================

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1.0"}],
    external_stylesheets=["https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap"]
)
app.title = "NairaShield AI - Fraud Analytics & Security Panel"

# Glassmorphic Layout Stylesheet
app.layout = html.Div(
    style={
        "backgroundColor": "#0b0f19",
        "color": "#f3f4f6",
        "fontFamily": "Outfit, sans-serif",
        "minHeight": "100vh",
        "padding": "2rem"
    },
    children=[
        # Title Header
        html.Header(
            style={
                "textAlign": "center",
                "marginBottom": "2rem",
                "position": "relative"
            },
            children=[
                html.H1(
                    "NairaShield AI Security Command",
                    style={
                        "fontSize": "3rem",
                        "fontWeight": "800",
                        "letterSpacing": "-0.05em",
                        "background": "linear-gradient(135deg, #10b981 0%, #3b82f6 100%)",
                        "WebkitBackgroundClip": "text",
                        "WebkitTextFillColor": "transparent",
                        "marginBottom": "0.3rem"
                    }
                ),
                html.P(
                    "CBN Regulations Verification, Real-Time Fraud Streams & Model Interpretability Hub",
                    style={"color": "#9ca3af", "fontSize": "1.1rem", "marginBottom": "1rem"}
                ),
                # ---- DOWNLOAD REPORT BUTTON ----
                html.Div(
                    style={"display": "flex", "justifyContent": "center", "gap": "1rem"},
                    children=[
                        html.Button(
                            id="btn-download-report",
                            n_clicks=0,
                            children=[
                                html.Span(
                                    "\u2193",
                                    style={"fontSize": "1.1rem", "marginRight": "0.5rem", "fontWeight": "700"}
                                ),
                                "Download Fraud Intelligence Report (PDF)"
                            ],
                            style={
                                "padding": "0.7rem 1.8rem",
                                "background": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                                "border": "none",
                                "borderRadius": "2rem",
                                "color": "#ffffff",
                                "fontWeight": "600",
                                "fontSize": "0.95rem",
                                "cursor": "pointer",
                                "boxShadow": "0 4px 20px rgba(16, 185, 129, 0.35)",
                                "fontFamily": "Outfit, sans-serif",
                                "letterSpacing": "0.02em",
                                "transition": "all 0.2s ease"
                            }
                        ),
                        html.Div(
                            id="report-status",
                            children="PDF report includes: KPIs, fraud patterns, model metrics, SHAP charts & flagged transactions.",
                            style={
                                "color": "#6b7280",
                                "fontSize": "0.8rem",
                                "display": "flex",
                                "alignItems": "center"
                            }
                        )
                    ]
                ),
                # Hidden download trigger
                dcc.Download(id="download-report")
            ]
        ),
        
        # Tabs for Navigation
        dcc.Tabs(
            id="nav-tabs",
            value="analytics-tab",
            children=[
                # Tab 1: Analytics Dashboard
                dcc.Tab(
                    label="Security Analytics Hub",
                    value="analytics-tab",
                    style={"backgroundColor": "#111827", "color": "#9ca3af", "border": "none", "fontFamily": "inherit", "fontSize": "1.1rem", "padding": "12px 24px"},
                    selected_style={"backgroundColor": "rgba(16, 185, 129, 0.15)", "color": "#10b981", "border": "none", "borderTop": "3px solid #10b981", "fontFamily": "inherit", "fontWeight": "600", "fontSize": "1.1rem", "padding": "12px 24px"},
                    children=[
                        # Metrics KPI row
                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "1fr 1fr 1fr",
                                "gap": "1.5rem",
                                "marginTop": "2rem",
                                "marginBottom": "2rem"
                            },
                            children=[
                                # Card 1
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(16, 185, 129, 0.2)",
                                        "borderRadius": "1.2rem",
                                        "padding": "1.5rem",
                                        "textAlign": "center",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[
                                        html.H3("Total Transactions Today", style={"color": "#9ca3af", "fontSize": "1rem", "fontWeight": "400", "marginBottom": "0.5rem"}),
                                        html.Div(f"{total_tx:,}", style={"fontSize": "2.4rem", "fontWeight": "800", "color": "#f3f4f6"})
                                    ]
                                ),
                                # Card 2
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(239, 68, 68, 0.2)",
                                        "borderRadius": "1.2rem",
                                        "padding": "1.5rem",
                                        "textAlign": "center",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[
                                        html.H3("Fraud Interceptions", style={"color": "#9ca3af", "fontSize": "1rem", "fontWeight": "400", "marginBottom": "0.5rem"}),
                                        html.Div(f"{flagged_count}", style={"fontSize": "2.4rem", "fontWeight": "800", "color": "#ef4444"})
                                    ]
                                ),
                                # Card 3
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(167, 139, 250, 0.2)",
                                        "borderRadius": "1.2rem",
                                        "padding": "1.5rem",
                                        "textAlign": "center",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[
                                        html.H3("Overall Fraud Rate", style={"color": "#9ca3af", "fontSize": "1rem", "fontWeight": "400", "marginBottom": "0.5rem"}),
                                        html.Div(f"{fraud_rate:.2f}%", style={"fontSize": "2.4rem", "fontWeight": "800", "color": "#a78bfa"})
                                    ]
                                )
                            ]
                        ),
                        
                        # Charts Grid Row 1
                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "1fr 1fr",
                                "gap": "2rem",
                                "marginBottom": "2rem"
                            },
                            children=[
                                # Trend Chart
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(255, 255, 255, 0.05)",
                                        "borderRadius": "1.5rem",
                                        "padding": "1.5rem",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[dcc.Graph(figure=make_fraud_trend_chart(), config={"displayModeBar": False})]
                                ),
                                # Geographic heat map
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(255, 255, 255, 0.05)",
                                        "borderRadius": "1.5rem",
                                        "padding": "1.5rem",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[dcc.Graph(figure=make_nigerian_heatmap(), config={"displayModeBar": False})]
                                )
                            ]
                        ),
                        
                        # Row 3: Bottom grid (Merchant bar chart + Sortable DataTable)
                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "1fr 1.5fr",
                                "gap": "2rem",
                                "marginBottom": "2rem"
                            },
                            children=[
                                # Merchant Chart
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(255, 255, 255, 0.05)",
                                        "borderRadius": "1.5rem",
                                        "padding": "1.5rem",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[dcc.Graph(figure=make_merchant_chart(), config={"displayModeBar": False})]
                                ),
                                
                                # Sortable table
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(255, 255, 255, 0.05)",
                                        "borderRadius": "1.5rem",
                                        "padding": "1.5rem",
                                        "backdropFilter": "blur(16px)",
                                        "display": "flex",
                                        "flexDirection": "column"
                                    },
                                    children=[
                                        html.H3("High-Risk Alerts Registry (Sortable & Filterable)", style={"fontSize": "1.1rem", "fontWeight": "600", "color": "#10b981", "marginBottom": "1rem"}),
                                        dash_table.DataTable(
                                            id="alerts-table",
                                            columns=[
                                                {"name": "Alert ID", "id": "alert_id"},
                                                {"name": "Timestamp", "id": "timestamp"},
                                                {"name": "Amount (NGN)", "id": "amount", "type": "numeric", "format": dash_table.FormatTemplate.money(0)},
                                                {"name": "Channel", "id": "channel"},
                                                {"name": "Location", "id": "location"},
                                                {"name": "Risk Index", "id": "risk_score", "type": "numeric", "format": dash_table.FormatTemplate.percentage(0)},
                                                {"name": "Status", "id": "status"}
                                            ],
                                            data=table_data,
                                            sort_action="native",
                                            sort_mode="multi",
                                            filter_action="native",
                                            page_action="native",
                                            page_size=5,
                                            style_table={'overflowX': 'auto'},
                                            style_cell={
                                                'backgroundColor': '#111827',
                                                'color': '#f3f4f6',
                                                'border': '1px solid rgba(255, 255, 255, 0.05)',
                                                'textAlign': 'left',
                                                'padding': '8px',
                                                'fontFamily': 'Outfit, sans-serif'
                                            },
                                            style_header={
                                                'backgroundColor': '#0f172a',
                                                'color': '#10b981',
                                                'fontWeight': 'bold',
                                                'border': '1px solid rgba(255, 255, 255, 0.1)'
                                            },
                                            style_data_conditional=[
                                                {
                                                    'if': {
                                                        'filter_query': '{status} eq "BLOCKED"',
                                                        'column_id': 'status'
                                                    },
                                                    'color': '#ef4444',
                                                    'fontWeight': 'bold'
                                                },
                                                {
                                                    'if': {
                                                        'filter_query': '{status} eq "PENDING_OTP"',
                                                        'column_id': 'status'
                                                    },
                                                    'color': '#f59e0b',
                                                    'fontWeight': 'bold'
                                                }
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                ),
                
                # Tab 2: SHAP Explanations
                dcc.Tab(
                    label="SHAP Model Interpreter",
                    value="shap-tab",
                    style={"backgroundColor": "#111827", "color": "#9ca3af", "border": "none", "fontFamily": "inherit", "fontSize": "1.1rem", "padding": "12px 24px"},
                    selected_style={"backgroundColor": "rgba(16, 185, 129, 0.15)", "color": "#10b981", "border": "none", "borderTop": "3px solid #10b981", "fontFamily": "inherit", "fontWeight": "600", "fontSize": "1.1rem", "padding": "12px 24px"},
                    children=[
                        # Grid Dashboard
                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "1fr 1.2fr",
                                "gap": "2rem",
                                "marginTop": "2rem",
                                "marginBottom": "2rem"
                            },
                            className="grid-container",
                            children=[
                                # Left Col: Inputs
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(16, 185, 129, 0.2)",
                                        "borderRadius": "1.5rem",
                                        "padding": "2rem",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[
                                        html.H2(
                                            "Simulate Transaction Profiler",
                                            style={
                                                "fontSize": "1.4rem",
                                                "fontWeight": "600",
                                                "color": "#10b981",
                                                "marginBottom": "1.5rem",
                                                "borderBottom": "1px solid rgba(255, 255, 255, 0.1)",
                                                "paddingBottom": "0.5rem"
                                            }
                                        ),
                                        # Amount
                                        html.Div(
                                            style={"marginBottom": "1.5rem"},
                                            children=[
                                                html.Label("Transaction Amount (NGN)", style={"color": "#9ca3af", "display": "block", "marginBottom": "0.5rem"}),
                                                dcc.Slider(
                                                    id="amount-slider",
                                                    min=0,
                                                    max=2500000,
                                                    step=50000,
                                                    value=1625000,
                                                    marks={
                                                        0: "₦0",
                                                        500000: "₦500k",
                                                        1000000: "₦1M",
                                                        1500000: "₦1.5M",
                                                        2000000: "₦2M",
                                                        2500000: "₦2.5M"
                                                    },
                                                    tooltip={"always_visible": True, "placement": "bottom"}
                                                )
                                            ]
                                        ),
                                        # Channel Dropdown
                                        html.Div(
                                            style={"marginBottom": "1.5rem"},
                                            children=[
                                                html.Label("Payment Channel Category", style={"color": "#9ca3af", "display": "block", "marginBottom": "0.5rem"}),
                                                dcc.Dropdown(
                                                    id="channel-dropdown",
                                                    options=[
                                                        {"label": "Mobile / Wire Transfer", "value": "channel_TRANSFER"},
                                                        {"label": "Card Web Checkout", "value": "channel_CARD_WEB"},
                                                        {"label": "Standard Debit Card", "value": "channel_DEBIT"},
                                                        {"label": "Card Host System", "value": "channel_CARD_HOST"},
                                                        {"label": "POS Cash Out", "value": "channel_CASH_OUT"},
                                                        {"label": "ATM Cash In", "value": "channel_CASH_IN"},
                                                        {"label": "Over-the-Counter Payment", "value": "channel_PAYMENT"},
                                                        {"label": "Card Recurring", "value": "channel_CARD_RECURRING"},
                                                        {"label": "Card Phone Attempt", "value": "channel_CARD_PHONE"},
                                                        {"label": "Card Store Terminal", "value": "channel_CARD_STORE"}
                                                    ],
                                                    value="channel_TRANSFER",
                                                    style={"color": "#0b0f19"}
                                                )
                                            ]
                                        ),
                                        # Source Dropdown
                                        html.Div(
                                            style={"marginBottom": "1.5rem"},
                                            children=[
                                                html.Label("Verification Pipeline Registry", style={"color": "#9ca3af", "display": "block", "marginBottom": "0.5rem"}),
                                                dcc.Dropdown(
                                                    id="source-dropdown",
                                                    options=[
                                                        {"label": "PaySim Registry Audit", "value": "source_dataset_PaySim"},
                                                        {"label": "IEEE-CIS Credit Audit", "value": "source_dataset_IEEE-CIS"}
                                                    ],
                                                    value="source_dataset_PaySim",
                                                    style={"color": "#0b0f19"}
                                                )
                                            ]
                                        ),
                                        # Button
                                        html.Button(
                                            "Calculate SHAP Explanation",
                                            id="submit-btn",
                                            n_clicks=0,
                                            style={
                                                "width": "100%",
                                                "padding": "1rem",
                                                "background": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                                                "border": "none",
                                                "borderRadius": "0.8rem",
                                                "color": "#ffffff",
                                                "fontWeight": "600",
                                                "fontSize": "1.1rem",
                                                "cursor": "pointer",
                                                "boxShadow": "0 5px 15px rgba(16, 185, 129, 0.3)"
                                            }
                                        )
                                    ]
                                ),
                                # Right Col: Waterfall
                                html.Div(
                                    style={
                                        "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                        "border": "1px solid rgba(16, 185, 129, 0.2)",
                                        "borderRadius": "1.5rem",
                                        "padding": "2rem",
                                        "backdropFilter": "blur(16px)"
                                    },
                                    children=[
                                        html.H2(
                                            "Local Waterfall Explanation",
                                            style={
                                                "fontSize": "1.4rem",
                                                "fontWeight": "600",
                                                "color": "#3b82f6",
                                                "marginBottom": "1.5rem",
                                                "borderBottom": "1px solid rgba(255, 255, 255, 0.1)",
                                                "paddingBottom": "0.5rem"
                                            }
                                        ),
                                        dcc.Graph(id="waterfall-graph", config={"displayModeBar": False})
                                    ]
                                )
                            ]
                        ),
                        
                        # Global Explanations (Row 2 in SHAP Tab)
                        html.Div(
                            style={
                                "backgroundColor": "rgba(17, 24, 39, 0.7)",
                                "border": "1px solid rgba(16, 185, 129, 0.1)",
                                "borderRadius": "1.5rem",
                                "padding": "2rem",
                                "backdropFilter": "blur(16px)"
                            },
                            children=[
                                html.H2(
                                    "Global Model Interpretability Panel",
                                    style={
                                        "fontSize": "1.6rem",
                                        "fontWeight": "600",
                                        "color": "#a78bfa",
                                        "marginBottom": "2rem",
                                        "borderBottom": "1px solid rgba(255, 255, 255, 0.1)",
                                        "paddingBottom": "0.5rem"
                                    }
                                ),
                                dcc.Tabs(
                                    id="shap-global-tabs",
                                    value="tab-importance",
                                    children=[
                                        dcc.Tab(
                                            label="Global Importance & Beeswarm Distribution",
                                            value="tab-importance",
                                            style={"backgroundColor": "#111827", "color": "#9ca3af", "border": "none", "fontFamily": "inherit"},
                                            selected_style={"backgroundColor": "rgba(167, 139, 250, 0.15)", "color": "#a78bfa", "border": "none", "borderTop": "2px solid #a78bfa", "fontFamily": "inherit", "fontWeight": "600"},
                                            children=[
                                                html.Div(
                                                    style={
                                                        "display": "grid",
                                                        "gridTemplateColumns": "1fr 1fr",
                                                        "gap": "1.5rem",
                                                        "paddingTop": "1.5rem"
                                                    },
                                                    children=[
                                                        dcc.Graph(id="importance-bar-graph", figure=make_importance_bar_chart()),
                                                        dcc.Graph(id="beeswarm-graph", figure=make_beeswarm_plot())
                                                    ]
                                                )
                                            ]
                                        ),
                                        dcc.Tab(
                                            label="Feature Dependence Relationships",
                                            value="tab-dependence",
                                            style={"backgroundColor": "#111827", "color": "#9ca3af", "border": "none", "fontFamily": "inherit"},
                                            selected_style={"backgroundColor": "rgba(167, 139, 250, 0.15)", "color": "#a78bfa", "border": "none", "borderTop": "2px solid #a78bfa", "fontFamily": "inherit", "fontWeight": "600"},
                                            children=[
                                                html.Div(
                                                    style={"paddingTop": "1.5rem"},
                                                    children=[
                                                        html.Div(
                                                            style={"width": "300px", "marginBottom": "1rem"},
                                                            children=[
                                                                html.Label("Select Feature for Dependence Plot:", style={"color": "#9ca3af", "display": "block", "marginBottom": "0.5rem"}),
                                                                dcc.Dropdown(
                                                                    id="dependence-dropdown",
                                                                    options=[{"label": f.replace("channel_", "Channel: ").replace("source_dataset_", "Pipeline: "), "value": f} for f in top_5_features],
                                                                    value=top_5_features[0] if top_5_features else None,
                                                                    style={"color": "#0b0f19"}
                                                                )
                                                            ]
                                                        ),
                                                        dcc.Graph(id="dependence-graph")
                                                    ]
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]
)

# =====================================================================
# CALLBACK INTERACTIVE ROUTINES
# =====================================================================

@app.callback(
    Output("dependence-graph", "figure"),
    [Input("dependence-dropdown", "value")]
)
def update_dependence(selected_feature):
    if not selected_feature:
        return go.Figure()
    return make_dependence_plot(selected_feature)

@app.callback(
    Output("waterfall-graph", "figure"),
    [Input("submit-btn", "n_clicks")],
    [
        State("amount-slider", "value"),
        State("channel-dropdown", "value"),
        State("source-dropdown", "value")
    ]
)
def update_waterfall(n_clicks, amount_val, channel_val, source_val):
    if model is None or explainer is None:
        fig = go.Figure()
        fig.add_annotation(text="Tuned Model not found. Run train_models.py first.", showarrow=False, font=dict(size=14, color="red"))
        fig.update_layout(paper_bgcolor='#0b0f19', plot_bgcolor='#0b0f19')
        return fig
    
    # 1. Rebuild the 13-feature input vector
    input_record = {}
    for name in feature_names:
        input_record[name] = 0.0
        
    input_record["amount"] = float(amount_val)
    input_record[channel_val] = 1.0
    input_record[source_val] = 1.0
    
    df_item = pd.DataFrame([input_record], columns=feature_names)
    
    try:
        # 2. Run SHAP TreeExplainer locally
        shap_res = explainer(df_item)
        base_value = float(explainer.expected_value)
        local_shap = shap_res.values[0]
        
        # 3. Sort features by absolute SHAP impact descending
        sorted_idx = np.argsort(np.abs(local_shap))[::-1]
        
        top_k = 8
        top_indices = sorted_idx[:top_k]
        other_indices = sorted_idx[top_k:]
        
        measures = ["absolute"]
        x_vals = [base_value]
        y_labels = ["Base Value"]
        
        cumulative = base_value
        
        # Top features
        for idx in top_indices:
            feat_name = feature_names[idx]
            feat_val = input_record[feat_name]
            shap_val = local_shap[idx]
            
            display_name = feat_name.replace("channel_", "").replace("source_dataset_", "")
            label = f"{display_name} = {feat_val:.2f}"
            
            measures.append("relative")
            x_vals.append(shap_val)
            y_labels.append(label)
            cumulative += shap_val
            
        # Group "Other" features
        if len(other_indices) > 0:
            other_shap_sum = sum(local_shap[idx] for idx in other_indices)
            measures.append("relative")
            x_vals.append(other_shap_sum)
            y_labels.append("5 Other Features")
            cumulative += other_shap_sum
            
        measures.append("total")
        x_vals.append(cumulative)
        y_labels.append("Prediction (Log-Odds)")
        
        prob = 1.0 / (1.0 + np.exp(-cumulative))
        
        fig = go.Figure(go.Waterfall(
            name="Inference explanation",
            orientation="h",
            measure=measures,
            x=x_vals,
            y=y_labels,
            connector={"line": {"color": "rgba(255, 255, 255, 0.15)"}},
            increasing={"marker": {"color": "#ef4444"}},
            decreasing={"marker": {"color": "#10b981"}},
            totals={"marker": {"color": "#3b82f6"}}
        ))
        
        fig.update_layout(
            title=f"SHAP Waterfall (Fraud Probability: {prob * 100:.2f}%)",
            xaxis_title="Prediction Log-Odds Impact",
            yaxis=dict(
                autorange="reversed",
                gridcolor='rgba(255, 255, 255, 0.05)',
                zerolinecolor='rgba(255, 255, 255, 0.1)'
            ),
            xaxis=dict(
                gridcolor='rgba(255, 255, 255, 0.05)',
                zerolinecolor='rgba(255, 255, 255, 0.1)'
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#f3f4f6', family='Outfit, sans-serif'),
            margin=dict(l=220, r=20, t=50, b=50),
            height=400
        )
        return fig
    except Exception as e:
        print(f"[Callback Error] Failed to calculate waterfall: {e}")
        return go.Figure()

# =====================================================================
# ENTRY POINT
# =====================================================================


# =====================================================================
# PDF REPORT DOWNLOAD CALLBACK
# =====================================================================

@app.callback(
    Output("download-report", "data"),
    Output("report-status", "children"),
    Output("report-status", "style"),
    Input("btn-download-report", "n_clicks"),
    prevent_initial_call=True
)
def download_pdf_report(n_clicks):
    """
    Generates the NairaShield PDF fraud intelligence report on button click
    and streams it back to the browser as a file download.
    """
    if not PDF_AVAILABLE:
        return (
            None,
            "Error: ReportLab not installed. Run: pip install reportlab",
            {"color": "#ef4444", "fontSize": "0.85rem", "display": "flex", "alignItems": "center"}
        )

    try:
        # ---- Assemble live data from dashboard globals ----

        # 1. Alerts (merge live + historical)
        live_alerts_raw = []
        if os.path.exists(ALERTS_PATH):
            try:
                with open(ALERTS_PATH, "r") as f:
                    live_alerts_raw = json.load(f)
            except Exception:
                pass

        alerts_for_report = []
        for a in live_alerts_raw:
            alerts_for_report.append({
                "alert_id":       a.get("alert_id", "N/A"),
                "transaction_id": a.get("transaction_id", "N/A"),
                "amount":         float(a.get("amount", 0)),
                "channel":        a.get("channel", "N/A"),
                "location":       a.get("location", "N/A"),
                "risk_score":     float(max(a.get("model_probability", 0), a.get("rule_risk_score", 0))),
                "status":         "BLOCKED" if max(a.get("model_probability", 0), a.get("rule_risk_score", 0)) >= 0.80 else "PENDING_OTP",
                "timestamp":      a.get("timestamp", "")[:19],
            })
        # Merge with historical seeded records
        alerts_for_report.extend(table_data)

        # 2. SHAP importance (from explainer if available, else fallback)
        shap_importance = DEFAULT_SHAP_IMPORTANCE
        if shap_values is not None and X_test is not None:
            mean_abs = float(abs(shap_values.values).mean())
            shap_importance = {
                col: float(shap_values.values[:, i].mean())
                for i, col in enumerate(X_test.columns)
            }

        # 3. Model metrics + fraud patterns use defaults (computed at train time)
        model_metrics   = DEFAULT_MODEL_METRICS
        fraud_patterns  = DEFAULT_FRAUD_PATTERNS

        # 4. Generate PDF
        pdf_bytes = generate_report(
            alerts=alerts_for_report,
            shap_importance=shap_importance,
            model_metrics=model_metrics,
            fraud_patterns=fraud_patterns,
            total_tx=total_tx,
            flagged=flagged_count,
            fraud_rate=fraud_rate,
            report_period=datetime.now().strftime("%d %B %Y"),
        )

        filename = f"NairaShield_Fraud_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        status_style = {
            "color": "#10b981",
            "fontSize": "0.85rem",
            "fontWeight": "600",
            "display": "flex",
            "alignItems": "center"
        }
        return (
            dcc.send_bytes(pdf_bytes, filename=filename),
            f"Report generated ({len(pdf_bytes) // 1024} KB) — downloading as {filename}",
            status_style
        )

    except Exception as e:
        err_style = {"color": "#ef4444", "fontSize": "0.85rem", "display": "flex", "alignItems": "center"}
        return None, f"Error generating report: {str(e)}", err_style


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060, debug=False)
