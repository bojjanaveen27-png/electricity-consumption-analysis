"""
Visualization module for Electricity Consumption Analysis System.
Generates Matplotlib charts for:
1. Overall monthly electricity consumption trend
2. Consumer comparison breakdown by type and volume
3. Regional consumption distribution
"""

from io import BytesIO
import matplotlib
# Use Agg backend for headless / server-side rendering
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Set consistent aesthetic style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

def create_empty_chart(message="No data available to display"):
    """
    Renders an informative placeholder when data is insufficient.
    """
    fig, ax = plt.subplots(figsize=(8, 4), dpi=120)
    ax.text(
        0.5, 0.5, message,
        ha="center", va="center", fontsize=12, color="#64748b",
        bbox=dict(boxstyle="round,pad=0.8", facecolor="#f8fafc", edgecolor="#cbd5e1")
    )
    ax.set_axis_off()
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_trend_chart(df):
    """
    Generates a line chart showing total monthly electricity consumption (kWh).
    """
    if df.empty:
        return create_empty_chart("No readings recorded yet.")

    valid = df[df["status"] == "VALID"].copy()
    if valid.empty:
        return create_empty_chart("No valid consecutive intervals available yet.")

    valid["month"] = valid["reading_date"].dt.to_period("M").dt.to_timestamp()
    monthly = valid.groupby("month")["analytical_kwh"].sum().reset_index()

    if monthly.empty:
        return create_empty_chart("Insufficient consecutive data for trend analysis.")

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=120)

    # Plot trend line and markers
    ax.plot(
        monthly["month"], monthly["analytical_kwh"],
        marker="o", markersize=6, linewidth=2.5, color="#0f766e",
        label="Monthly Total (kWh)"
    )
    # Shaded area under the curve
    ax.fill_between(monthly["month"], monthly["analytical_kwh"], color="#0f766e", alpha=0.12)

    # Value labels on markers
    for _, row in monthly.iterrows():
        ax.annotate(
            f"{row['analytical_kwh']:,.0f} kWh",
            (row["month"], row["analytical_kwh"]),
            textcoords="offset points",
            xytext=(0, 9),
            ha="center",
            fontsize=8.5,
            fontweight="600",
            color="#0f172a"
        )

    ax.set_title("System-Wide Monthly Electricity Consumption Trend", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Billing / Reading Period", fontsize=10, fontweight="600")
    ax.set_ylabel("Total Consumption (kWh)", fontsize=10, fontweight="600")
    ax.grid(True, linestyle="--", alpha=0.5)

    # Format dates on x-axis
    fig.autofmt_xdate(rotation=20)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_consumer_comparison_chart(df):
    """
    Generates a horizontal bar chart comparing consumption among consumers,
    colored by consumer type (Residential, Commercial, Industrial).
    """
    if df.empty:
        return create_empty_chart("No readings recorded yet.")

    valid = df[df["status"] == "VALID"].copy()
    if valid.empty:
        return create_empty_chart("No valid intervals available for comparison.")

    # Aggregate by consumer
    summary = valid.groupby(
        ["consumer_id", "consumer_type", "region"],
        as_index=False
    )["analytical_kwh"].sum()

    if summary.empty:
        return create_empty_chart("No consumption data available.")

    summary["label"] = summary.apply(
        lambda r: f"#{r['consumer_id']} ({r['consumer_type'][:3]} - {r['region']})", axis=1
    )
    summary = summary.sort_values("analytical_kwh", ascending=True)

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=120)

    # Assign distinct colors per consumer type
    color_map = {
        "residential": "#3b82f6",
        "commercial": "#f59e0b",
        "industrial": "#8b5cf6"
    }
    bar_colors = [color_map.get(t.lower(), "#0f766e") for t in summary["consumer_type"]]

    bars = ax.barh(summary["label"], summary["analytical_kwh"], color=bar_colors, height=0.55)

    # Annotate bar values
    for bar in bars:
        width = bar.get_width()
        ax.annotate(
            f" {width:,.1f} kWh",
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(4, 0),
            textcoords="offset points",
            ha="left", va="center",
            fontsize=8.5, fontweight="600", color="#334155"
        )

    ax.set_title("Total Consumption by Consumer (kWh)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Cumulative Valid Consumption (kWh)", fontsize=10, fontweight="600")
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)

    # Custom legend for consumer types
    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(color="#3b82f6", label="Residential"),
        mpatches.Patch(color="#f59e0b", label="Commercial"),
        mpatches.Patch(color="#8b5cf6", label="Industrial")
    ]
    ax.legend(handles=legend_handles, loc="lower right", framealpha=0.9)

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_regional_breakdown_chart(df):
    """
    Generates a donut chart representing electricity consumption by geographic region.
    """
    if df.empty:
        return create_empty_chart("No readings recorded yet.")

    valid = df[df["status"] == "VALID"].copy()
    if valid.empty:
        return create_empty_chart("No valid intervals available.")

    reg_summary = valid.groupby("region")["analytical_kwh"].sum().reset_index()
    if reg_summary.empty or reg_summary["analytical_kwh"].sum() == 0:
        return create_empty_chart("Insufficient consumption for regional breakdown.")

    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)

    palette = ["#0f766e", "#0284c7", "#8b5cf6", "#f59e0b", "#ec4899", "#10b981"]
    colors = palette[:len(reg_summary)]

    wedges, texts, autotexts = ax.pie(
        reg_summary["analytical_kwh"],
        labels=reg_summary["region"],
        autopct="%1.1f%%",
        startangle=140,
        colors=colors,
        pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2)
    )

    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(9)
        at.set_weight("bold")

    for t in texts:
        t.set_fontsize(10)
        t.set_weight("500")

    ax.set_title("Consumption Distribution by Region", fontsize=13, fontweight="bold", pad=12)

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf
