"""
Analytical engine for Electricity Consumption Analysis System.
Leverages Pandas for period grouping and NumPy for consumption,
rate of change, and chronological validation calculations.
"""

import pandas as pd
import numpy as np
from database import execute_query
import config

def get_readings_dataframe():
    """
    Fetches all meter readings joined with meter and consumer metadata.
    Applies NumPy and Pandas logic to calculate consecutive consumption,
    validate chronological sequence, and flag resets or rollovers.
    """
    sql = """
        SELECT 
            r.reading_id,
            r.meter_id,
            m.meter_code,
            c.consumer_id,
            c.consumer_type,
            c.region,
            r.reading_date,
            r.cumulative_kwh
        FROM meter_readings r
        JOIN meters m ON m.meter_id = r.meter_id
        JOIN consumers c ON c.consumer_id = m.consumer_id
        ORDER BY r.meter_id, r.reading_date ASC, r.reading_id ASC
    """
    rows = execute_query(sql)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Data type normalization
    df["reading_date"] = pd.to_datetime(df["reading_date"])
    df["cumulative_kwh"] = pd.to_numeric(df["cumulative_kwh"], errors="coerce").fillna(0.0)

    # Calculate consecutive intervals per meter
    df["previous_kwh"] = df.groupby("meter_id")["cumulative_kwh"].shift(1)
    df["previous_date"] = df.groupby("meter_id")["reading_date"].shift(1)
    df["consumption_kwh"] = df["cumulative_kwh"] - df["previous_kwh"]
    df["days_between"] = (df["reading_date"] - df["previous_date"]).dt.days

    # Validation conditions using NumPy select
    conditions = [
        df["previous_kwh"].isna(),           # First reading has no baseline
        df["days_between"] <= 0,             # Same date or backward in time
        df["consumption_kwh"] < 0            # Cumulative reading decreased (rollover / reset)
    ]
    choices = [
        "FIRST READING",
        "INVALID DATE ORDER",
        "RESET/ROLLOVER REVIEW"
    ]
    df["status"] = np.select(conditions, choices, default="VALID")

    # Only VALID readings count toward analytical consumption
    df["analytical_kwh"] = np.where(df["status"] == "VALID", df["consumption_kwh"], np.nan)

    # Calculate daily average burn rate (kWh/day) for valid intervals
    df["daily_avg_kwh"] = np.where(
        (df["status"] == "VALID") & (df["days_between"] > 0),
        df["consumption_kwh"] / df["days_between"],
        np.nan
    )

    return df

def get_monthly_consumption_summary(df):
    """
    Summarizes consumption by calendar month using Pandas period grouping (dt.to_period('M')).
    Computes Month-over-Month (MoM) consumption change per consumer.
    """
    if df.empty:
        return pd.DataFrame()

    valid = df[df["status"] == "VALID"].copy()
    if valid.empty:
        return pd.DataFrame()

    # Assign period based on the later reading date in the consecutive interval
    valid["month"] = valid["reading_date"].dt.to_period("M").astype(str)

    # Group by month and consumer attributes
    grouped = valid.groupby(
        ["month", "consumer_id", "consumer_type", "region"],
        as_index=False
    ).agg(
        consumption_kwh=("analytical_kwh", "sum"),
        reading_count=("reading_id", "count"),
        total_days=("days_between", "sum"),
        avg_daily_kwh=("daily_avg_kwh", "mean")
    )

    grouped["consumption_kwh"] = grouped["consumption_kwh"].round(2)
    grouped["avg_daily_kwh"] = grouped["avg_daily_kwh"].round(2)

    # Sort to compute Month-over-Month (MoM) change percentage per consumer
    grouped = grouped.sort_values(["consumer_id", "month"]).reset_index(drop=True)
    grouped["mom_change_pct"] = grouped.groupby("consumer_id")["consumption_kwh"].pct_change() * 100.0
    grouped["mom_change_pct"] = grouped["mom_change_pct"].replace([np.inf, -np.inf], np.nan).round(1)

    # Final presentation sort (latest months first)
    grouped = grouped.sort_values(["month", "consumer_id"], ascending=[False, True]).reset_index(drop=True)
    return grouped

def get_yearly_consumption_summary(df):
    """
    Summarizes consumption by calendar year using Pandas period grouping (dt.to_period('Y')).
    """
    if df.empty:
        return pd.DataFrame()

    valid = df[df["status"] == "VALID"].copy()
    if valid.empty:
        return pd.DataFrame()

    valid["year"] = valid["reading_date"].dt.to_period("Y").astype(str)
    yearly = valid.groupby(
        ["year", "consumer_id", "consumer_type", "region"],
        as_index=False
    ).agg(
        total_consumption_kwh=("analytical_kwh", "sum"),
        reading_count=("reading_id", "count"),
        avg_reading_kwh=("analytical_kwh", "mean")
    )

    yearly["total_consumption_kwh"] = yearly["total_consumption_kwh"].round(2)
    yearly["avg_reading_kwh"] = yearly["avg_reading_kwh"].round(2)
    yearly = yearly.sort_values(["year", "consumer_id"], ascending=[False, True]).reset_index(drop=True)
    return yearly

def get_high_usage_analysis(monthly_df, threshold_kwh=None):
    """
    Identifies consumers and months where consumption equals or exceeds a configurable threshold.
    """
    if threshold_kwh is None:
        threshold_kwh = config.DEFAULT_HIGH_USAGE_THRESHOLD_KWH

    if monthly_df.empty:
        return pd.DataFrame()

    high_usage = monthly_df[monthly_df["consumption_kwh"] >= threshold_kwh].copy()
    if high_usage.empty:
        return pd.DataFrame()

    high_usage["excess_kwh"] = (high_usage["consumption_kwh"] - threshold_kwh).round(2)
    high_usage["pct_above_threshold"] = (
        ((high_usage["consumption_kwh"] - threshold_kwh) / threshold_kwh) * 100.0
    ).round(1)

    return high_usage.sort_values("consumption_kwh", ascending=False).reset_index(drop=True)

def get_validation_report(df):
    """
    Produces audit log of non-valid readings (First readings, Rollover reviews, Date sequence errors).
    Documents diagnostic notes and assumptions for each record.
    """
    if df.empty:
        return pd.DataFrame()

    flagged = df[df["status"] != "VALID"].copy()
    if flagged.empty:
        return pd.DataFrame()

    def generate_audit_note(row):
        status = row["status"]
        if status == "FIRST READING":
            return "Baseline reading registered. Consecutive interval consumption will start with next reading."
        elif status == "RESET/ROLLOVER REVIEW":
            diff = row["consumption_kwh"]
            return f"Cumulative value dropped by {abs(diff):.2f} kWh. Possible meter replacement or mechanical 99999 rollover."
        elif status == "INVALID DATE ORDER":
            return "Reading date is earlier than or equal to the prior reading date."
        return "Unspecified validation flag."

    flagged["audit_note"] = flagged.apply(generate_audit_note, axis=1)
    flagged["reading_date_str"] = flagged["reading_date"].dt.strftime("%Y-%m-%d")
    flagged["previous_date_str"] = flagged["previous_date"].dt.strftime("%Y-%m-%d").fillna("N/A")
    flagged["previous_kwh_display"] = flagged["previous_kwh"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "None")

    return flagged.sort_values(["meter_id", "reading_date"], ascending=[True, False]).reset_index(drop=True)

def get_system_kpis(df, threshold_kwh=None):
    """
    Calculates summary metrics for dashboard cards.
    """
    if threshold_kwh is None:
        threshold_kwh = config.DEFAULT_HIGH_USAGE_THRESHOLD_KWH

    consumers_count = execute_query("SELECT COUNT(*) AS n FROM consumers")[0]["n"]
    meters_count = execute_query("SELECT COUNT(*) AS n FROM meters")[0]["n"]
    readings_count = execute_query("SELECT COUNT(*) AS n FROM meter_readings")[0]["n"]

    if df.empty:
        return {
            "consumers": consumers_count,
            "meters": meters_count,
            "readings": readings_count,
            "total_kwh": 0.0,
            "avg_monthly_kwh": 0.0,
            "high_usage_count": 0,
            "flagged_count": 0
        }

    valid_mask = df["status"] == "VALID"
    total_kwh = float(df.loc[valid_mask, "analytical_kwh"].sum()) if valid_mask.any() else 0.0
    flagged_count = int((~valid_mask).sum())

    monthly_df = get_monthly_consumption_summary(df)
    avg_monthly_kwh = float(monthly_df["consumption_kwh"].mean()) if not monthly_df.empty else 0.0
    high_df = get_high_usage_analysis(monthly_df, threshold_kwh)
    high_usage_count = len(high_df)

    return {
        "consumers": consumers_count,
        "meters": meters_count,
        "readings": readings_count,
        "total_kwh": round(total_kwh, 2),
        "avg_monthly_kwh": round(avg_monthly_kwh, 2),
        "high_usage_count": high_usage_count,
        "flagged_count": flagged_count
    }
