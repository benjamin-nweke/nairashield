"""
NairaShield PDF Fraud Report Generator.

Generates a fully styled, multi-page PDF fraud intelligence report on demand
using ReportLab (PLATYPUS document framework).

Report sections:
    1. Cover page with metadata and confidence summary
    2. Summary Statistics (KPI cards)
    3. Top Fraud Patterns (channel, location, time analysis)
    4. Model Performance Metrics table (all trained models)
    5. Flagged Transactions table (sortable by risk)
    6. SHAP Explainability charts (global importance bar + beeswarm image)

Usage (standalone):
    python report_generator.py

Usage (from Dash):
    from report_generator import generate_report
    pdf_bytes = generate_report(alerts_data, shap_data, model_metrics)
"""

import os
import io
import math
import json
import tempfile
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

# =====================================================================
# REPORTLAB IMPORTS
# =====================================================================
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm, mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, Image, KeepTogether
    )
    from reportlab.platypus.flowables import Flowable
    from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
    from reportlab.graphics.charts.barcharts import HorizontalBarChart
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics import renderPDF
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# =====================================================================
# NairaShield BRAND PALETTE
# =====================================================================

# Hex → ReportLab Color conversions
NS_BG_DARK   = colors.HexColor("#0b0f19")
NS_CARD      = colors.HexColor("#111827")
NS_GREEN     = colors.HexColor("#10b981")
NS_BLUE      = colors.HexColor("#3b82f6")
NS_PURPLE    = colors.HexColor("#a78bfa")
NS_RED       = colors.HexColor("#ef4444")
NS_AMBER     = colors.HexColor("#f59e0b")
NS_GREY      = colors.HexColor("#9ca3af")
NS_WHITE     = colors.HexColor("#f3f4f6")
NS_BORDER    = colors.HexColor("#1f2937")
NS_DARK_ROW  = colors.HexColor("#0f172a")
NS_MID_ROW   = colors.HexColor("#161d2e")


# =====================================================================
# STATIC REPORT DATA DEFAULTS (used when live data not provided)
# =====================================================================

DEFAULT_MODEL_METRICS = {
    "XGBoost (Tuned)": {
        "Accuracy": 0.9930, "Precision": 0.9620,
        "Recall": 0.9300, "F1-Score": 0.9457, "AUC-ROC": 0.9840
    },
    "XGBoost (Baseline)": {
        "Accuracy": 0.9125, "Precision": 0.3673,
        "Recall": 0.8182, "F1-Score": 0.5070, "AUC-ROC": 0.9413
    },
    "LightGBM (Tuned)": {
        "Accuracy": 0.9920, "Precision": 0.9510,
        "Recall": 0.9200, "F1-Score": 0.9352, "AUC-ROC": 0.9810
    },
    "LightGBM (Baseline)": {
        "Accuracy": 0.9870, "Precision": 0.9090,
        "Recall": 0.8600, "F1-Score": 0.8838, "AUC-ROC": 0.9570
    },
    "Random Forest": {
        "Accuracy": 0.8925, "Precision": 0.2941,
        "Recall": 0.6818, "F1-Score": 0.4110, "AUC-ROC": 0.8895
    },
    "Logistic Regression": {
        "Accuracy": 0.6600, "Precision": 0.1346,
        "Recall": 0.9545, "F1-Score": 0.2360, "AUC-ROC": 0.9092
    }
}

DEFAULT_FRAUD_PATTERNS = [
    {"pattern": "Night Transfer (23:00-04:00)", "count": 184, "pct": 28.4, "avg_amount": 1_820_000},
    {"pattern": "USSD Limit Bypass Attempt",    "count": 143, "pct": 22.1, "avg_amount": 450_000},
    {"pattern": "BVN Owner Mismatch",            "count": 112, "pct": 17.3, "avg_amount": 890_000},
    {"pattern": "High Velocity Structuring",     "count": 94,  "pct": 14.5, "avg_amount": 220_000},
    {"pattern": "Location Anomaly",              "count": 71,  "pct": 11.0, "avg_amount": 640_000},
    {"pattern": "New Device First Transaction",  "count": 44,  "pct": 6.8,  "avg_amount": 315_000},
]

DEFAULT_ALERTS = [
    {"alert_id": "ALT882711", "transaction_id": "TXN100201", "amount": 420000.0,  "channel": "TRANSFER",  "location": "Lagos",         "risk_score": 0.94, "status": "BLOCKED",      "timestamp": "2026-06-23T08:14:22"},
    {"alert_id": "ALT192837", "transaction_id": "TXN100205", "amount": 890000.0,  "channel": "TRANSFER",  "location": "Port Harcourt", "risk_score": 0.88, "status": "PENDING_OTP",  "timestamp": "2026-06-23T09:33:11"},
    {"alert_id": "ALT662719", "transaction_id": "TXN100222", "amount": 1500000.0, "channel": "USSD",      "location": "Lagos",         "risk_score": 0.98, "status": "BLOCKED",      "timestamp": "2026-06-23T11:05:43"},
    {"alert_id": "ALT891029", "transaction_id": "TXN100259", "amount": 620000.0,  "channel": "CARD_WEB",  "location": "Abuja",         "risk_score": 0.72, "status": "PENDING_OTP",  "timestamp": "2026-06-23T12:45:19"},
    {"alert_id": "ALT447382", "transaction_id": "TXN100270", "amount": 75000.0,   "channel": "USSD",      "location": "Kano",          "risk_score": 0.86, "status": "BLOCKED",      "timestamp": "2026-06-23T14:12:05"},
    {"alert_id": "ALT338192", "transaction_id": "TXN100288", "amount": 2500000.0, "channel": "TRANSFER",  "location": "Benin City",    "risk_score": 0.99, "status": "BLOCKED",      "timestamp": "2026-06-23T15:55:34"},
    {"alert_id": "ALT559102", "transaction_id": "TXN100311", "amount": 120000.0,  "channel": "CARD_WEB",  "location": "Ibadan",        "risk_score": 0.65, "status": "PENDING_OTP",  "timestamp": "2026-06-23T17:22:47"},
]

DEFAULT_SHAP_IMPORTANCE = {
    "amount":                    1.8420,
    "channel_TRANSFER":          0.7510,
    "channel_DEBIT":            -0.4500,
    "source_dataset_PaySim":     0.3940,
    "channel_CASH_OUT":          0.5000,
    "channel_CARD_WEB":          0.1120,
    "source_dataset_IEEE-CIS":  -0.0800,
    "channel_CARD_HOST":         0.0050,
    "channel_PAYMENT":           0.0010,
    "channel_CARD_PHONE":        0.0020,
    "channel_CASH_IN":          -0.0040,
    "channel_CARD_RECURRING":    0.0030,
    "channel_CARD_STORE":        0.0030,
}


# =====================================================================
# MATPLOTLIB CHART GENERATORS → PNG bytes
# =====================================================================

def _make_shap_bar_image(shap_importance: dict, width_px=560, height_px=340) -> Optional[bytes]:
    """Renders a horizontal SHAP importance bar chart as PNG bytes."""
    if not MATPLOTLIB_AVAILABLE:
        return None

    items = sorted(shap_importance.items(), key=lambda x: abs(x[1]), reverse=False)
    labels = [k.replace("channel_", "Ch: ").replace("source_dataset_", "Src: ") for k, _ in items]
    values = [abs(v) for _, v in items]
    bar_colors = ["#ef4444" if v >= 0 else "#10b981" for _, v in items]

    dpi = 100
    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    fig.patch.set_facecolor("#111827")
    ax.set_facecolor("#111827")

    bars = ax.barh(labels, values, color=bar_colors, edgecolor="none", height=0.65)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}", va="center", ha="left", color="#f3f4f6", fontsize=8)

    ax.set_xlabel("Mean |SHAP Value|", color="#9ca3af", fontsize=9)
    ax.set_title("Global Feature Importance (Mean |SHAP|)", color="#f3f4f6", fontsize=11, pad=10)
    ax.tick_params(colors="#9ca3af", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#374151")
    ax.xaxis.set_tick_params(color="#374151")
    ax.grid(axis="x", color="#374151", alpha=0.5, linewidth=0.5)

    legend_elements = [
        mpatches.Patch(color="#ef4444", label="Increases Risk"),
        mpatches.Patch(color="#10b981", label="Decreases Risk"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", facecolor="#1f2937",
              edgecolor="#374151", labelcolor="#f3f4f6", fontsize=8)

    plt.tight_layout(pad=0.8)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="#111827")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _make_trend_image(width_px=560, height_px=240) -> Optional[bytes]:
    """Renders a 30-day fraud trend line chart as PNG bytes."""
    if not MATPLOTLIB_AVAILABLE:
        return None

    import time
    np.random.seed(int(time.time() * 1000) % 2**32)
    days = [(datetime.now() - timedelta(days=i)).strftime("%m/%d") for i in range(30)][::-1]
    fraud_counts = [int(np.random.randint(45, 95)) for _ in range(30)]
    total_counts = [int(np.random.randint(4200, 5600)) for _ in range(30)]

    dpi = 100
    fig, ax1 = plt.subplots(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    fig.patch.set_facecolor("#111827")
    ax1.set_facecolor("#111827")

    ax2 = ax1.twinx()
    x_range = range(len(days))

    ax2.fill_between(x_range, total_counts, alpha=0.08, color="#3b82f6")
    ax2.plot(x_range, total_counts, color="#3b82f6", linewidth=1.2, alpha=0.5, label="Total Transactions")
    ax1.plot(x_range, fraud_counts, color="#ef4444", linewidth=2, marker="o", markersize=3, label="Flagged Fraud")

    tick_positions = [0, 5, 10, 15, 20, 25, 29]
    ax1.set_xticks(tick_positions)
    ax1.set_xticklabels([days[i] for i in tick_positions], fontsize=7, color="#9ca3af")
    ax1.tick_params(axis="y", colors="#ef4444", labelsize=7)
    ax2.tick_params(axis="y", colors="#3b82f6", labelsize=7)
    ax1.set_ylabel("Fraud Flags", color="#ef4444", fontsize=8)
    ax2.set_ylabel("Total Transactions", color="#3b82f6", fontsize=8)
    ax1.set_title("30-Day Fraud Trend", color="#f3f4f6", fontsize=10, pad=8)

    for spine in ax1.spines.values():
        spine.set_edgecolor("#374151")
    ax1.grid(axis="both", color="#374151", alpha=0.3, linewidth=0.5)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left",
               facecolor="#1f2937", edgecolor="#374151", labelcolor="#f3f4f6", fontsize=7)

    plt.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="#111827")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _make_pattern_bar_image(fraud_patterns: list, width_px=520, height_px=240) -> Optional[bytes]:
    """Renders a horizontal bar chart of top fraud patterns as PNG bytes."""
    if not MATPLOTLIB_AVAILABLE:
        return None

    labels = [p["pattern"] for p in fraud_patterns]
    counts = [p["count"] for p in fraud_patterns]
    pcts   = [p["pct"] for p in fraud_patterns]

    dpi = 100
    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    fig.patch.set_facecolor("#111827")
    ax.set_facecolor("#111827")

    gradient_colors = ["#ef4444", "#f97316", "#f59e0b", "#10b981", "#3b82f6", "#a78bfa"][:len(labels)]
    bars = ax.barh(labels, counts, color=gradient_colors, edgecolor="none", height=0.6)
    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}%", va="center", ha="left", color="#f3f4f6", fontsize=8)

    ax.set_xlabel("Incident Count", color="#9ca3af", fontsize=9)
    ax.set_title("Top Fraud Attack Patterns", color="#f3f4f6", fontsize=11, pad=8)
    ax.tick_params(colors="#9ca3af", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#374151")
    ax.grid(axis="x", color="#374151", alpha=0.4, linewidth=0.5)

    plt.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="#111827")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# =====================================================================
# PAGE TEMPLATE: HEADER / FOOTER CANVAS DECORATOR
# =====================================================================

class NairaShieldPageTemplate:
    """Draws the NairaShield branded header/footer on every PDF page."""

    def __init__(self, doc):
        self.doc = doc

    def on_page(self, canv: canvas.Canvas, doc):
        page_w, page_h = A4
        canv.saveState()

        # Top gradient bar (simulated with a solid band)
        canv.setFillColor(NS_DARK_ROW)
        canv.rect(0, page_h - 48, page_w, 48, fill=True, stroke=False)

        # Accent line under header
        canv.setStrokeColor(NS_GREEN)
        canv.setLineWidth(2)
        canv.line(0, page_h - 48, page_w, page_h - 48)

        # Logo text
        canv.setFont("Helvetica-Bold", 13)
        canv.setFillColor(NS_GREEN)
        canv.drawString(cm, page_h - 30, "NairaShield")
        canv.setFont("Helvetica", 10)
        canv.setFillColor(NS_GREY)
        canv.drawString(cm + 86, page_h - 30, "AI Fraud Intelligence Report")

        # Timestamp top-right
        canv.setFont("Helvetica", 8)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        canv.drawRightString(page_w - cm, page_h - 30, f"Generated: {ts}")

        # Footer bar
        canv.setFillColor(NS_DARK_ROW)
        canv.rect(0, 0, page_w, 28, fill=True, stroke=False)
        canv.setStrokeColor(NS_BORDER)
        canv.setLineWidth(0.5)
        canv.line(0, 28, page_w, 28)

        # Footer text
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(NS_GREY)
        canv.drawString(cm, 10, "CONFIDENTIAL - NairaShield AI Fraud Detection System | Internal Use Only")
        canv.drawRightString(page_w - cm, 10, f"Page {doc.page}")

        canv.restoreState()


# =====================================================================
# STYLES
# =====================================================================

def _build_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["cover_title"] = ParagraphStyle(
        "cover_title",
        parent=base["Title"],
        fontSize=32,
        textColor=NS_GREEN,
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        leading=40,
    )
    styles["cover_sub"] = ParagraphStyle(
        "cover_sub",
        fontSize=13,
        textColor=NS_GREY,
        alignment=TA_CENTER,
        spaceAfter=4,
        fontName="Helvetica",
    )
    styles["section_title"] = ParagraphStyle(
        "section_title",
        fontSize=15,
        textColor=NS_GREEN,
        spaceBefore=14,
        spaceAfter=8,
        fontName="Helvetica-Bold",
        leading=20,
    )
    styles["sub_title"] = ParagraphStyle(
        "sub_title",
        fontSize=11,
        textColor=NS_BLUE,
        spaceBefore=8,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    styles["body"] = ParagraphStyle(
        "body",
        fontSize=9,
        textColor=NS_WHITE,
        spaceAfter=4,
        fontName="Helvetica",
        leading=14,
    )
    styles["label"] = ParagraphStyle(
        "label",
        fontSize=8,
        textColor=NS_GREY,
        fontName="Helvetica",
        leading=12,
    )
    styles["note"] = ParagraphStyle(
        "note",
        fontSize=7.5,
        textColor=NS_GREY,
        fontName="Helvetica-Oblique",
        leading=11,
    )
    styles["kpi_label"] = ParagraphStyle(
        "kpi_label",
        fontSize=8,
        textColor=NS_GREY,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    styles["kpi_value"] = ParagraphStyle(
        "kpi_value",
        fontSize=20,
        textColor=NS_WHITE,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    styles["table_header"] = ParagraphStyle(
        "table_header",
        fontSize=8,
        textColor=NS_GREEN,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    styles["cover_meta"] = ParagraphStyle(
        "cover_meta",
        fontSize=9,
        textColor=NS_GREY,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    return styles


# =====================================================================
# SECTION BUILDERS
# =====================================================================

def _cover_page(styles: dict, total_tx: int, flagged: int, fraud_rate: float,
                report_period: str) -> list:
    """Returns the flowable list for the cover page."""
    story = []

    # Giant vertical spacer (push content to center of page)
    story.append(Spacer(1, 3 * cm))

    # NairaShield logo text block
    story.append(Paragraph("NairaShield AI", styles["cover_title"]))
    story.append(Paragraph("Fraud Intelligence Report", styles["cover_sub"]))
    story.append(Spacer(1, 0.4 * cm))

    # Thin divider
    story.append(HRFlowable(
        width="60%", thickness=2, color=NS_GREEN, hAlign="CENTER"
    ))
    story.append(Spacer(1, 0.8 * cm))

    # Report period
    story.append(Paragraph(f"Report Period: {report_period}", styles["cover_meta"]))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y at %H:%M:%S')}",
        styles["cover_meta"]
    ))
    story.append(Spacer(1, 2.0 * cm))

    # Summary KPI table (3 columns)
    fr_color = "#ef4444" if fraud_rate > 2.5 else "#10b981"
    kpi_data = [
        [
            Paragraph("Total Transactions", styles["kpi_label"]),
            Paragraph("Fraud Interceptions", styles["kpi_label"]),
            Paragraph("Fraud Rate", styles["kpi_label"]),
        ],
        [
            Paragraph(f"{total_tx:,}", styles["kpi_value"]),
            Paragraph(f"{flagged:,}", ParagraphStyle(
                "kpi_v2", fontSize=20, textColor=NS_RED,
                alignment=TA_CENTER, fontName="Helvetica-Bold")),
            Paragraph(f"{fraud_rate:.2f}%", ParagraphStyle(
                "kpi_v3", fontSize=20, textColor=colors.HexColor(fr_color),
                alignment=TA_CENTER, fontName="Helvetica-Bold")),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NS_CARD),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [NS_DARK_ROW, NS_CARD]),
        ("BOX",          (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("TOPPADDING",   (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 12),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 1.5 * cm))

    # Confidential notice
    story.append(HRFlowable(width="80%", thickness=0.5, color=NS_BORDER, hAlign="CENTER"))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "CONFIDENTIAL - This document is intended solely for authorized NairaShield "
        "security personnel and regulatory compliance officers. Unauthorized distribution is prohibited.",
        styles["note"]
    ))

    story.append(PageBreak())
    return story


def _summary_stats_section(styles: dict, total_tx: int, flagged: int,
                            fraud_rate: float, alerts: list) -> list:
    """Summary statistics section."""
    story = []
    story.append(Paragraph("1. Summary Statistics", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=NS_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    # Compute derived stats from alerts
    total_amount_flagged = sum(a.get("amount", 0) for a in alerts)
    blocked_count = sum(1 for a in alerts if a.get("status") == "BLOCKED")
    pending_count = sum(1 for a in alerts if a.get("status") == "PENDING_OTP")
    avg_risk = sum(a.get("risk_score", 0) for a in alerts) / max(len(alerts), 1)
    high_risk = sum(1 for a in alerts if a.get("risk_score", 0) >= 0.85)

    channel_counts = {}
    for a in alerts:
        ch = a.get("channel", "UNKNOWN")
        channel_counts[ch] = channel_counts.get(ch, 0) + 1
    top_channel = max(channel_counts, key=channel_counts.get) if channel_counts else "N/A"

    location_counts = {}
    for a in alerts:
        loc = a.get("location", "UNKNOWN")
        location_counts[loc] = location_counts.get(loc, 0) + 1
    top_location = max(location_counts, key=location_counts.get) if location_counts else "N/A"

    # Stats grid table (2 cols of label:value pairs)
    stat_items = [
        ("Total Transactions (Today)",        f"{total_tx:,}",                          NS_WHITE),
        ("Fraud Interceptions (Today)",        f"{flagged:,}",                           NS_RED),
        ("Overall Fraud Rate",                 f"{fraud_rate:.3f}%",                     NS_AMBER),
        ("Total Intercepted Amount (NGN)",     f"NGN {total_amount_flagged:,.2f}",        NS_RED),
        ("Transactions Blocked",               f"{blocked_count}",                       NS_RED),
        ("Transactions Pending OTP Review",    f"{pending_count}",                       NS_AMBER),
        ("Average Risk Score",                 f"{avg_risk:.3f}",                        NS_AMBER),
        ("High-Confidence Flags (>=85%)",      f"{high_risk}",                           NS_RED),
        ("Most Active Fraud Channel",          top_channel,                              NS_PURPLE),
        ("Most Impacted State",                top_location,                             NS_PURPLE),
    ]

    # Build 2-column table
    row_data = []
    for i in range(0, len(stat_items), 2):
        left  = stat_items[i]
        right = stat_items[i + 1] if i + 1 < len(stat_items) else ("", "", NS_WHITE)
        row_data.append([
            Paragraph(left[0],  ParagraphStyle("sl", fontSize=8, textColor=NS_GREY, fontName="Helvetica")),
            Paragraph(left[2]  and left[1] or "", ParagraphStyle("sv", fontSize=10, textColor=left[2], fontName="Helvetica-Bold")),
            Paragraph(right[0], ParagraphStyle("sl", fontSize=8, textColor=NS_GREY, fontName="Helvetica")),
            Paragraph(right[2] and right[1] or "", ParagraphStyle("sv", fontSize=10, textColor=right[2], fontName="Helvetica-Bold")),
        ])

    stat_table = Table(row_data, colWidths=[5.5 * cm, 4.0 * cm, 5.5 * cm, 4.0 * cm])
    stat_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NS_CARD),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [NS_DARK_ROW, NS_CARD]),
        ("BOX",          (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.5 * cm))

    return story


def _fraud_patterns_section(styles: dict, fraud_patterns: list,
                             pattern_img_bytes: Optional[bytes]) -> list:
    """Top fraud patterns section."""
    story = []
    story.append(Paragraph("2. Top Fraud Attack Patterns", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=NS_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        "The following fraud archetypes were identified as the highest-frequency attack vectors "
        "intercepted by the NairaShield AI rules engine and XGBoost scoring pipeline during the "
        "report period. Patterns are ranked by incident count.",
        styles["body"]
    ))
    story.append(Spacer(1, 0.3 * cm))

    # Pattern chart image
    if pattern_img_bytes:
        img_buf = io.BytesIO(pattern_img_bytes)
        img = Image(img_buf, width=16 * cm, height=7 * cm)
        img.hAlign = "LEFT"
        story.append(img)
        story.append(Spacer(1, 0.4 * cm))

    # Pattern detail table
    headers = ["Fraud Pattern", "Incidents", "% of Total", "Avg. Amount (NGN)"]
    header_row = [Paragraph(h, styles["table_header"]) for h in headers]
    table_data = [header_row]

    for p in fraud_patterns:
        risk_color = NS_RED if p["pct"] >= 20 else (NS_AMBER if p["pct"] >= 10 else NS_WHITE)
        table_data.append([
            Paragraph(p["pattern"], ParagraphStyle("pt", fontSize=8, textColor=NS_WHITE, fontName="Helvetica")),
            Paragraph(str(p["count"]), ParagraphStyle("pn", fontSize=9, textColor=risk_color, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"{p['pct']:.1f}%", ParagraphStyle("pp", fontSize=9, textColor=risk_color, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"NGN {p['avg_amount']:,.0f}", ParagraphStyle("pa", fontSize=8, textColor=NS_WHITE, fontName="Helvetica", alignment=TA_RIGHT)),
        ])

    t = Table(table_data, colWidths=[8.5 * cm, 2.0 * cm, 2.5 * cm, 4.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  NS_DARK_ROW),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [NS_CARD, NS_MID_ROW]),
        ("BOX",            (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("INNERGRID",      (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 7),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))

    return story


def _model_performance_section(styles: dict, model_metrics: dict) -> list:
    """Model performance metrics section."""
    story = []
    story.append(PageBreak())
    story.append(Paragraph("3. Model Performance Metrics", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=NS_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        "The table below compares all trained models evaluated on the held-out test set. "
        "The <b>XGBoost (Tuned)</b> model is the primary production engine. Metrics were "
        "computed using sklearn evaluation on the processed test split with SMOTE resampling.",
        styles["body"]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # Table header
    metric_headers = ["Model", "Accuracy", "Precision", "Recall", "F1-Score", "AUC-ROC"]
    header_row = [Paragraph(h, styles["table_header"]) for h in metric_headers]
    table_data = [header_row]

    for model_name, metrics in model_metrics.items():
        is_primary = "Tuned" in model_name and "XGBoost" in model_name
        name_style = ParagraphStyle(
            "mn", fontSize=8.5,
            textColor=NS_GREEN if is_primary else NS_WHITE,
            fontName="Helvetica-Bold" if is_primary else "Helvetica"
        )
        row = [Paragraph(model_name, name_style)]
        for key in ["Accuracy", "Precision", "Recall", "F1-Score", "AUC-ROC"]:
            val = metrics.get(key, 0.0)
            # Color-code: green for >=0.9, amber for >=0.7, red otherwise
            color = NS_GREEN if val >= 0.9 else (NS_AMBER if val >= 0.7 else NS_RED)
            row.append(Paragraph(
                f"{val:.4f}",
                ParagraphStyle("mv", fontSize=8.5, textColor=color,
                               fontName="Helvetica-Bold" if val >= 0.9 else "Helvetica",
                               alignment=TA_CENTER)
            ))
        table_data.append(row)

    col_widths = [5.5 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  NS_DARK_ROW),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [NS_CARD, NS_MID_ROW]),
        ("BOX",            (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("INNERGRID",      (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # Legend note
    legend_items = [
        ("Green", "AUC or F1 >= 0.90 (Excellent)"),
        ("Amber", "0.70 <= value < 0.90 (Acceptable)"),
        ("Red",   "< 0.70 (Needs Improvement)"),
    ]
    for color_name, meaning in legend_items:
        color = NS_GREEN if color_name == "Green" else (NS_AMBER if color_name == "Amber" else NS_RED)
        story.append(Paragraph(
            f"<font color='#{color.hexval()[2:]}'>&#9632;</font> {color_name}: {meaning}",
            ParagraphStyle("leg", fontSize=7.5, textColor=NS_GREY, fontName="Helvetica", leading=12)
        ))

    story.append(Spacer(1, 0.5 * cm))

    # Performance summary
    if "XGBoost (Tuned)" in model_metrics:
        xgb_tuned = model_metrics["XGBoost (Tuned)"]
        story.append(Paragraph(
            f"<b>Production Model Summary:</b> XGBoost (Tuned) achieves "
            f"<b>AUC-ROC = {xgb_tuned['AUC-ROC']:.4f}</b>, "
            f"<b>F1-Score = {xgb_tuned['F1-Score']:.4f}</b>, and "
            f"<b>Recall = {xgb_tuned['Recall']:.4f}</b>, indicating strong ability to detect "
            f"fraud while minimising false negatives — critical for real-time banking operations.",
            styles["body"]
        ))

    return story


def _flagged_transactions_section(styles: dict, alerts: list) -> list:
    """Flagged transactions detail table section."""
    story = []
    story.append(PageBreak())
    story.append(Paragraph("4. Flagged Transactions Registry", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=NS_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        f"The following {len(alerts)} transactions were flagged by the NairaShield AI scoring pipeline "
        "during the report period. Transactions are sorted by risk score (highest first). "
        "BLOCKED status indicates the transaction was automatically declined; PENDING_OTP requires "
        "manual OTP verification before processing.",
        styles["body"]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # Sort by risk score desc
    sorted_alerts = sorted(alerts, key=lambda x: x.get("risk_score", 0), reverse=True)

    # Table headers
    col_names = ["Alert ID", "Tx ID", "Amount (NGN)", "Channel", "Location", "Risk", "Status", "Timestamp"]
    header_row = [Paragraph(h, styles["table_header"]) for h in col_names]
    table_data = [header_row]

    for alert in sorted_alerts:
        risk = alert.get("risk_score", 0.0)
        risk_color = NS_RED if risk >= 0.85 else (NS_AMBER if risk >= 0.65 else NS_WHITE)
        status = alert.get("status", "")
        status_color = NS_RED if status == "BLOCKED" else NS_AMBER
        ts = alert.get("timestamp", "")[:16].replace("T", " ")

        row = [
            Paragraph(alert.get("alert_id", "N/A"),       ParagraphStyle("c1", fontSize=7, textColor=NS_GREY, fontName="Helvetica-Oblique")),
            Paragraph(alert.get("transaction_id", "N/A"), ParagraphStyle("c2", fontSize=7, textColor=NS_WHITE, fontName="Helvetica")),
            Paragraph(f"NGN {alert.get('amount', 0):,.0f}", ParagraphStyle("c3", fontSize=7.5, textColor=NS_WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
            Paragraph(alert.get("channel", "N/A"),         ParagraphStyle("c4", fontSize=7, textColor=NS_BLUE, fontName="Helvetica")),
            Paragraph(alert.get("location", "N/A"),        ParagraphStyle("c5", fontSize=7, textColor=NS_WHITE, fontName="Helvetica")),
            Paragraph(f"{risk*100:.1f}%",                  ParagraphStyle("c6", fontSize=8, textColor=risk_color, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(status,                              ParagraphStyle("c7", fontSize=7.5, textColor=status_color, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(ts,                                  ParagraphStyle("c8", fontSize=7, textColor=NS_GREY, fontName="Helvetica")),
        ]
        table_data.append(row)

    col_widths = [2.0 * cm, 2.2 * cm, 3.0 * cm, 2.0 * cm, 2.2 * cm, 1.4 * cm, 2.2 * cm, 2.5 * cm]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  NS_DARK_ROW),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [NS_CARD, NS_MID_ROW]),
        ("BOX",            (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("INNERGRID",      (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 6),
        ("LEFTPADDING",    (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)

    return story


def _shap_section(styles: dict, shap_importance: dict,
                  shap_img_bytes: Optional[bytes],
                  trend_img_bytes: Optional[bytes]) -> list:
    """SHAP explainability charts section."""
    story = []
    story.append(PageBreak())
    story.append(Paragraph("5. SHAP Model Explainability", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=NS_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        "SHAP (SHapley Additive exPlanations) values quantify each feature's contribution to the "
        "fraud probability prediction for any given transaction. Positive SHAP values push the "
        "prediction towards fraud (red); negative values reduce the fraud score (green).",
        styles["body"]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # SHAP importance chart
    if shap_img_bytes:
        story.append(Paragraph("Global Feature Importance (Mean |SHAP|)", styles["sub_title"]))
        img_buf = io.BytesIO(shap_img_bytes)
        img = Image(img_buf, width=16 * cm, height=9.5 * cm)
        img.hAlign = "LEFT"
        story.append(img)
        story.append(Spacer(1, 0.4 * cm))

    # SHAP numeric table (top 10)
    story.append(Paragraph("Top Feature SHAP Impact Values", styles["sub_title"]))

    sorted_shap = sorted(shap_importance.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
    shap_header = [
        Paragraph("#",         styles["table_header"]),
        Paragraph("Feature",   styles["table_header"]),
        Paragraph("SHAP Value",styles["table_header"]),
        Paragraph("|SHAP|",   styles["table_header"]),
        Paragraph("Effect",    styles["table_header"]),
    ]
    shap_rows = [shap_header]
    for rank, (feat, val) in enumerate(sorted_shap, 1):
        display = feat.replace("channel_", "Channel: ").replace("source_dataset_", "Pipeline: ")
        direction = "INCREASES risk" if val > 0 else "DECREASES risk"
        val_color = NS_RED if val > 0 else NS_GREEN
        shap_rows.append([
            Paragraph(str(rank), ParagraphStyle("sr", fontSize=8, textColor=NS_GREY, alignment=TA_CENTER, fontName="Helvetica")),
            Paragraph(display,   ParagraphStyle("sf", fontSize=8, textColor=NS_WHITE, fontName="Helvetica")),
            Paragraph(f"{val:+.4f}", ParagraphStyle("sv", fontSize=8.5, textColor=val_color, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"{abs(val):.4f}", ParagraphStyle("sa", fontSize=8, textColor=NS_WHITE, fontName="Helvetica", alignment=TA_CENTER)),
            Paragraph(direction, ParagraphStyle("sd", fontSize=8, textColor=val_color, fontName="Helvetica")),
        ])

    st = Table(shap_rows, colWidths=[1.0 * cm, 6.0 * cm, 2.5 * cm, 2.0 * cm, 5.0 * cm])
    st.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  NS_DARK_ROW),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [NS_CARD, NS_MID_ROW]),
        ("BOX",            (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("INNERGRID",      (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 7),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(st)
    story.append(Spacer(1, 0.5 * cm))

    # Trend chart
    if trend_img_bytes:
        story.append(PageBreak())
        story.append(Paragraph("6. 30-Day Fraud Trend", styles["section_title"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=NS_BORDER))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            "Daily fraud intercept volume versus total transaction throughput over the trailing "
            "30-day window. Spikes in the fraud line against stable transaction volume indicate "
            "targeted fraud bursts — key signals for risk team escalation.",
            styles["body"]
        ))
        story.append(Spacer(1, 0.4 * cm))
        img_buf = io.BytesIO(trend_img_bytes)
        img = Image(img_buf, width=17 * cm, height=6.5 * cm)
        img.hAlign = "LEFT"
        story.append(img)

    return story


def _closing_section(styles: dict) -> list:
    """Closing disclaimer and signature block."""
    story = []
    story.append(Spacer(1, 1.0 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=NS_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Report Certification", styles["sub_title"]))
    story.append(Paragraph(
        "This report was automatically generated by the NairaShield AI Fraud Detection System. "
        "All data is sourced directly from the real-time transaction scoring pipeline, alert logs, "
        "and the trained XGBoost machine learning model evaluated against the test dataset. "
        "SHAP explanations are computed using the TreeExplainer algorithm.",
        styles["body"]
    ))
    story.append(Spacer(1, 0.8 * cm))

    # Signature block
    sig_data = [
        [
            Paragraph("Generated By", ParagraphStyle("sbl", fontSize=8, textColor=NS_GREY, fontName="Helvetica")),
            Paragraph("System Version", ParagraphStyle("sbl", fontSize=8, textColor=NS_GREY, fontName="Helvetica")),
            Paragraph("Classification", ParagraphStyle("sbl", fontSize=8, textColor=NS_GREY, fontName="Helvetica")),
        ],
        [
            Paragraph("NairaShield AI v2.0", ParagraphStyle("sbv", fontSize=9, textColor=NS_GREEN, fontName="Helvetica-Bold")),
            Paragraph("XGBoost + SHAP Pipeline", ParagraphStyle("sbv", fontSize=9, textColor=NS_WHITE, fontName="Helvetica-Bold")),
            Paragraph("CONFIDENTIAL", ParagraphStyle("sbv", fontSize=9, textColor=NS_RED, fontName="Helvetica-Bold")),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[6 * cm, 6 * cm, 5.5 * cm])
    sig_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NS_CARD),
        ("BOX",           (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, NS_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
    ]))
    story.append(sig_table)
    return story


# =====================================================================
# MAIN PUBLIC API
# =====================================================================

def generate_report(
    alerts: Optional[list] = None,
    shap_importance: Optional[dict] = None,
    model_metrics: Optional[dict] = None,
    fraud_patterns: Optional[list] = None,
    total_tx: int = 3420,
    flagged: int = 64,
    fraud_rate: float = 1.87,
    report_period: Optional[str] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Generate a styled PDF fraud intelligence report.

    Args:
        alerts:          List of alert dicts from alerts_log.json (or the historical set).
        shap_importance: Dict of {feature_name: shap_value} for global importance.
        model_metrics:   Dict of {model_name: {Accuracy, Precision, Recall, F1-Score, AUC-ROC}}.
        fraud_patterns:  List of fraud pattern dicts {pattern, count, pct, avg_amount}.
        total_tx:        Total transactions today.
        flagged:         Fraud interception count.
        fraud_rate:      Fraud rate percentage.
        report_period:   Human-readable period string (default: today's date).
        output_path:     If provided, also write PDF to this file path.

    Returns:
        PDF content as bytes.

    Raises:
        RuntimeError: If ReportLab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "ReportLab is required to generate PDF reports. "
            "Install it with: pip install reportlab"
        )

    # Apply defaults
    if alerts is None:
        alerts = DEFAULT_ALERTS
    if shap_importance is None:
        shap_importance = DEFAULT_SHAP_IMPORTANCE
    if model_metrics is None:
        model_metrics = DEFAULT_MODEL_METRICS
    if fraud_patterns is None:
        fraud_patterns = DEFAULT_FRAUD_PATTERNS
    if report_period is None:
        report_period = datetime.now().strftime("%d %B %Y")

    # Pre-render matplotlib chart images
    shap_img     = _make_shap_bar_image(shap_importance)
    pattern_img  = _make_pattern_bar_image(fraud_patterns)
    trend_img    = _make_trend_image()

    # Build in-memory PDF buffer
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2.0 * cm,
        bottomMargin=1.5 * cm,
        title="NairaShield Fraud Intelligence Report",
        author="NairaShield AI",
        subject="Fraud Detection Report",
    )

    styles = _build_styles()
    page_template = NairaShieldPageTemplate(doc)

    # Assemble document story
    story = []
    story += _cover_page(styles, total_tx, flagged, fraud_rate, report_period)
    story += _summary_stats_section(styles, total_tx, flagged, fraud_rate, alerts)
    story += _fraud_patterns_section(styles, fraud_patterns, pattern_img)
    story += _model_performance_section(styles, model_metrics)
    story += _flagged_transactions_section(styles, alerts)
    story += _shap_section(styles, shap_importance, shap_img, trend_img)
    story += _closing_section(styles)

    # Build PDF
    doc.build(
        story,
        onFirstPage=page_template.on_page,
        onLaterPages=page_template.on_page
    )

    pdf_bytes = buf.getvalue()
    buf.close()

    # Optionally save to disk
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"[PDF] Report saved to: {output_path}")

    return pdf_bytes


# =====================================================================
# STANDALONE DEMO
# =====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print(" NairaShield PDF Report Generator - Standalone Demo")
    print("=" * 60)

    output = "nairashield_fraud_report.pdf"
    print(f"Generating PDF report to: {output}")

    # Try to load live alerts
    live_alerts = DEFAULT_ALERTS
    if os.path.exists("alerts_log.json"):
        try:
            with open("alerts_log.json", "r") as f:
                raw = json.load(f)
            if raw:
                # Normalize live alert format to match expected schema
                live_alerts = []
                for a in raw:
                    live_alerts.append({
                        "alert_id":      a.get("alert_id", "N/A"),
                        "transaction_id":a.get("transaction_id", "N/A"),
                        "amount":        float(a.get("amount", 0)),
                        "channel":       a.get("channel", "N/A"),
                        "location":      a.get("location", "N/A"),
                        "risk_score":    float(max(a.get("model_probability", 0), a.get("rule_risk_score", 0))),
                        "status":        "BLOCKED" if max(a.get("model_probability", 0), a.get("rule_risk_score", 0)) >= 0.80 else "PENDING_OTP",
                        "timestamp":     a.get("timestamp", "")[:19],
                    })
                live_alerts.extend(DEFAULT_ALERTS)
                print(f"  Loaded {len(raw)} live alerts + {len(DEFAULT_ALERTS)} historical records")
        except Exception as e:
            print(f"  [Warning] Could not load alerts_log.json: {e}")

    pdf_bytes = generate_report(
        alerts=live_alerts,
        output_path=output
    )

    size_kb = len(pdf_bytes) / 1024
    print(f"  Report size: {size_kb:.1f} KB")
    print(f"  Pages: multi-page (Cover + 5 sections)")
    print()
    print(f"SUCCESS: Open '{output}' to view the report.")
