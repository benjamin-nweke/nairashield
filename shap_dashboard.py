"""
NairaShield Interactive SHAP Explainability Dashboard.
Built using Plotly Dash.
Provides global feature importance, beeswarm plots, feature dependence plots,
and a per-transaction waterfall explanation updated dynamically.
"""

import os
import numpy as np
import pandas as pd
import joblib
import shap
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import plotly.express as px

# =====================================================================
# DATA & MODEL INITIALIZATION
# =====================================================================

MODEL_PATH = "xgboost_model_tuned.joblib"
DATA_PATH = "test.csv"

# Global states
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
    print("[Error] Missing tuned model or test dataset. Run train_models.py first.")

# Standard feature template
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
# CHART GENERATORS
# =====================================================================

def make_importance_bar_chart():
    if shap_values is None or X_test is None:
        return go.Figure()
    
    mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
    importance_df = pd.DataFrame({
        "Feature": X_test.columns,
        "Importance": mean_abs_shap
    }).sort_values(by="Importance", ascending=True)
    
    # Visual formatting of feature names for readability
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
    sorted_idx = np.argsort(mean_abs_shap) # sort ascending for y-axis mapping
    
    features_sorted = X_test.columns[sorted_idx]
    
    plot_x = []
    plot_y = []
    plot_color = []
    plot_hover = []
    
    np.random.seed(42)
    # Sample up to 250 rows to keep rendering and interaction snappy
    sample_size = min(len(X_test), 250)
    indices = np.random.choice(len(X_test), size=sample_size, replace=False)
    
    for y_val, feat_idx in enumerate(sorted_idx):
        feat_name = X_test.columns[feat_idx]
        display_name = feat_name.replace("channel_", "").replace("source_dataset_", "")
        
        vals = X_test.iloc[indices, feat_idx].values
        shaps = shap_vals[indices, feat_idx]
        
        # Add random vertical jitter within (-0.25, 0.25) to see density
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
            colorscale='RdBu_r', # Blue to Red
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
    
    # Generate dependence data
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
app.title = "NairaShield AI - SHAP Interpretability Portal"

server = app.server

# Beautiful CSS Styling
app.layout = html.Div(
    style={
        "backgroundColor": "#0b0f19",
        "color": "#f3f4f6",
        "fontFamily": "Outfit, sans-serif",
        "minHeight": "100vh",
        "padding": "2rem"
    },
    children=[
        # Header
        html.Header(
            style={"textAlign": "center", "marginBottom": "2rem"},
            children=[
                html.H1(
                    "NairaShield AI SHAP Interpreter",
                    style={
                        "fontSize": "2.8rem",
                        "fontWeight": "800",
                        "letterSpacing": "-0.05em",
                        "background": "linear-gradient(135deg, #10b981 0%, #3b82f6 100%)",
                        "WebkitBackgroundClip": "text",
                        "WebkitTextFillColor": "transparent",
                        "marginBottom": "0.3rem"
                    }
                ),
                html.P(
                    "Interactive Explainability Center for Real-time Fraud Detection Algorithms",
                    style={"color": "#9ca3af", "fontSize": "1.1rem"}
                )
            ]
        ),
        
        # Grid Dashboard
        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr 1.2fr",
                "gap": "2rem",
                "marginBottom": "2rem"
            },
            className="grid-container",
            children=[
                # Column 1: Predictor Panel
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
                        
                        # Amount input slider
                        html.Div(
                            style={"marginBottom": "1.5rem"},
                            children=[
                                html.Label("Transaction Amount (Normalized: 0.0 - 1.0)", style={"color": "#9ca3af", "display": "block", "marginBottom": "0.5rem"}),
                                dcc.Slider(
                                    id="amount-slider",
                                    min=0.0,
                                    max=1.0,
                                    step=0.01,
                                    value=0.65,
                                    marks={0: "0.0", 0.5: "0.5", 1: "1.0"},
                                    tooltip={"always_visible": True, "placement": "bottom"}
                                )
                            ]
                        ),
                        
                        # Channel dropdown
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
                        
                        # Source footprint
                        html.Div(
                            style={"marginBottom": "1.5rem"},
                            children=[
                                html.Label("Verification Pipeline registry", style={"color": "#9ca3af", "display": "block", "marginBottom": "0.5rem"}),
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
                
                # Column 2: Waterfall Visual Panel
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
        
        # Row 2: Global Interpretability Center
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
                    id="tabs",
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
        # Fallback when model files are not created
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
        
        # We will separate top 8 features and bin the remaining 5 to keep the chart clean
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
            increasing={"marker": {"color": "#ef4444"}}, # Red for risk increase
            decreasing={"marker": {"color": "#10b981"}}, # Green for risk decrease
            totals={"marker": {"color": "#3b82f6"}} # Blue for total
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
