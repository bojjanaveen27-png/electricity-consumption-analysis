"""
Electricity Consumption Analysis System
Main Flask Application

Provides web routes for:
- Consumer and meter record management
- Dated cumulative meter reading ingestion with validation
- Interval consumption calculation (handling first readings and rollovers)
- Monthly and yearly usage aggregation via Pandas
- Anomaly / high-usage identification with configurable threshold
- Matplotlib analytical charts (Trends, Consumer comparisons, Regional breakdown)
- CSV reporting and audit logs
"""

from datetime import date
import io
import csv
import pandas as pd
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_file, Response
)
import config
from database import (
    get_active_engine, execute_query, init_db, seed_sample_data
)
import analysis
import visualization

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

# Ensure database tables exist on startup
try:
    init_db()
except Exception as e:
    print(f"[Startup Warning] Could not initialize DB immediately: {e}")

@app.context_processor
def inject_global_metadata():
    """
    Injects global context into all templates.
    """
    return {
        "active_engine": get_active_engine(),
        "default_threshold": config.DEFAULT_HIGH_USAGE_THRESHOLD_KWH,
        "kwh_unit": "kWh"
    }

@app.route("/")
def dashboard():
    """
    Overview dashboard: KPI metrics, charts, and summary statistics.
    """
    try:
        threshold = float(request.args.get("threshold", config.DEFAULT_HIGH_USAGE_THRESHOLD_KWH))
        df = analysis.get_readings_dataframe()
        kpis = analysis.get_system_kpis(df, threshold)

        return render_template(
            "dashboard.html",
            kpis=kpis,
            threshold=threshold
        )
    except Exception as e:
        return render_template("error.html", message=f"Failed to load dashboard: {e}")

@app.route("/consumers", methods=["GET", "POST"])
def consumers_page():
    """
    Consumer records management: list and add consumers.
    """
    if request.method == "POST":
        consumer_type = request.form.get("consumer_type", "").strip()
        region = request.form.get("region", "").strip()

        if not consumer_type or not region:
            flash("Consumer type and region are required fields.", "error")
            return redirect(url_for("consumers_page"))

        try:
            execute_query(
                "INSERT INTO consumers (consumer_type, region) VALUES (%s, %s)",
                (consumer_type, region),
                fetch=False
            )
            flash(f"Successfully added consumer ({consumer_type} - {region}).", "success")
        except Exception as e:
            flash(f"Error adding consumer: {e}", "error")

        return redirect(url_for("consumers_page"))

    # Fetch consumer list with meter counts
    sql = """
        SELECT c.consumer_id, c.consumer_type, c.region, c.created_at,
               COUNT(m.meter_id) AS meter_count
        FROM consumers c
        LEFT JOIN meters m ON c.consumer_id = m.consumer_id
        GROUP BY c.consumer_id, c.consumer_type, c.region, c.created_at
        ORDER BY c.consumer_id DESC
    """
    consumers = execute_query(sql)
    return render_template("consumers.html", consumers=consumers)

@app.route("/meters", methods=["GET", "POST"])
def meters_page():
    """
    Meter records management: register meters associated with consumers.
    """
    if request.method == "POST":
        try:
            consumer_id = int(request.form.get("consumer_id", 0))
            meter_code = request.form.get("meter_code", "").strip().upper()

            if not meter_code:
                raise ValueError("Meter code cannot be empty.")

            # Check if meter_code already exists
            existing = execute_query("SELECT meter_id FROM meters WHERE meter_code = %s", (meter_code,))
            if existing:
                raise ValueError(f"Meter code '{meter_code}' is already registered.")

            execute_query(
                "INSERT INTO meters (consumer_id, meter_code) VALUES (%s, %s)",
                (consumer_id, meter_code),
                fetch=False
            )
            flash(f"Meter '{meter_code}' successfully linked to Consumer #{consumer_id}.", "success")
        except Exception as e:
            flash(f"Could not register meter: {e}", "error")

        return redirect(url_for("meters_page"))

    consumers = execute_query(
        "SELECT consumer_id, consumer_type, region FROM consumers ORDER BY consumer_id ASC"
    )
    sql = """
        SELECT m.meter_id, m.meter_code, m.consumer_id, m.created_at,
               c.consumer_type, c.region,
               COUNT(r.reading_id) AS reading_count
        FROM meters m
        JOIN consumers c ON c.consumer_id = m.consumer_id
        LEFT JOIN meter_readings r ON r.meter_id = m.meter_id
        GROUP BY m.meter_id, m.meter_code, m.consumer_id, m.created_at, c.consumer_type, c.region
        ORDER BY m.meter_id DESC
    """
    meters = execute_query(sql)
    return render_template("meters.html", consumers=consumers, meters=meters)

@app.route("/readings", methods=["GET", "POST"])
def readings_page():
    """
    Meter reading ingestion and validation.
    Checks chronological validity and alerts on meter resets or rollovers.
    """
    if request.method == "POST":
        try:
            meter_id = int(request.form.get("meter_id", 0))
            reading_date_str = request.form.get("reading_date", "").strip()
            kwh_str = request.form.get("cumulative_kwh", "").strip()

            if not reading_date_str:
                raise ValueError("Reading date is required.")
            reading_date = date.fromisoformat(reading_date_str)

            kwh = float(kwh_str)
            if kwh < 0:
                raise ValueError("Cumulative reading must be non-negative (>= 0 kWh).")

            # Validate against prior readings for this meter
            prior = execute_query(
                """
                SELECT reading_date, cumulative_kwh 
                FROM meter_readings 
                WHERE meter_id = %s 
                ORDER BY reading_date DESC, reading_id DESC 
                LIMIT 1
                """,
                (meter_id,)
            )

            is_rollover = False
            if prior:
                last_date_val = prior[0]["reading_date"]
                last_date = date.fromisoformat(str(last_date_val)) if not isinstance(last_date_val, date) else last_date_val
                last_kwh = float(prior[0]["cumulative_kwh"])

                if reading_date <= last_date:
                    raise ValueError(
                        f"Chronological validation error: Reading date ({reading_date}) must be later "
                        f"than the previous reading date ({last_date}) for this meter."
                    )

                if kwh < last_kwh:
                    is_rollover = True
                    # Allowed to be saved, but will be flagged for review in analytics
                    flash(
                        f"Notice: Cumulative reading ({kwh:.2f} kWh) is lower than previous reading ({last_kwh:.2f} kWh). "
                        "Reading saved, but flagged under 'RESET/ROLLOVER REVIEW' in reports.",
                        "warning"
                    )

            # Insert reading
            execute_query(
                "INSERT INTO meter_readings (meter_id, reading_date, cumulative_kwh) VALUES (%s, %s, %s)",
                (meter_id, reading_date, kwh),
                fetch=False
            )
            if not is_rollover:
                flash("Meter reading recorded successfully.", "success")

        except Exception as e:
            flash(f"Error saving reading: {e}", "error")

        return redirect(url_for("readings_page"))

    meters = execute_query(
        """
        SELECT m.meter_id, m.meter_code, c.consumer_type, c.region 
        FROM meters m 
        JOIN consumers c ON c.consumer_id = m.consumer_id 
        ORDER BY m.meter_code ASC
        """
    )
    
    # Fetch recent readings with analytical status
    df = analysis.get_readings_dataframe()
    recent_readings = []
    if not df.empty:
        # Sort descending by date for display
        display_df = df.sort_values(["reading_date", "reading_id"], ascending=[False, False]).head(50)
        display_df["reading_date_str"] = display_df["reading_date"].dt.strftime("%Y-%m-%d")
        recent_readings = display_df.to_dict("records")

    return render_template(
        "readings.html",
        meters=meters,
        readings=recent_readings
    )

@app.route("/reports")
def reports():
    """
    Comprehensive analytical reports:
    1. Monthly consumption summary with MoM change
    2. Yearly consumption summary
    3. High-usage anomaly detection (with dynamic threshold)
    4. Reading validation and rollover audit log
    """
    try:
        threshold = float(request.args.get("threshold", config.DEFAULT_HIGH_USAGE_THRESHOLD_KWH))
        df = analysis.get_readings_dataframe()

        monthly_df = analysis.get_monthly_consumption_summary(df)
        yearly_df = analysis.get_yearly_consumption_summary(df)
        high_usage_df = analysis.get_high_usage_analysis(monthly_df, threshold)
        validation_df = analysis.get_validation_report(df)

        return render_template(
            "reports.html",
            threshold=threshold,
            monthly=monthly_df.to_dict("records") if not monthly_df.empty else [],
            yearly=yearly_df.to_dict("records") if not yearly_df.empty else [],
            high_usage=high_usage_df.to_dict("records") if not high_usage_df.empty else [],
            validation=validation_df.to_dict("records") if not validation_df.empty else []
        )
    except Exception as e:
        return render_template("error.html", message=f"Failed to generate reports: {e}")

@app.route("/reports/export/monthly")
def export_monthly_csv():
    """
    Exports the calculated monthly consumption report as a downloadable CSV.
    """
    df = analysis.get_readings_dataframe()
    monthly_df = analysis.get_monthly_consumption_summary(df)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Month", "Consumer ID", "Consumer Type", "Region",
        "Consumption (kWh)", "Reading Intervals", "Avg Daily (kWh)", "MoM Change (%)"
    ])

    if not monthly_df.empty:
        for _, row in monthly_df.iterrows():
            writer.writerow([
                row.get("month", ""),
                row.get("consumer_id", ""),
                row.get("consumer_type", ""),
                row.get("region", ""),
                f"{row.get('consumption_kwh', 0):.2f}",
                row.get("reading_count", 0),
                f"{row.get('avg_daily_kwh', 0):.2f}" if pd.notna(row.get('avg_daily_kwh')) else "N/A",
                f"{row.get('mom_change_pct', 0):.1f}%" if pd.notna(row.get('mom_change_pct')) else "N/A"
            ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=monthly_electricity_consumption_report.csv"}
    )

# ----------------- Visualizations Endpoints -----------------

@app.route("/chart/trend.png")
def chart_trend():
    """
    Streams monthly usage trend line chart.
    """
    df = analysis.get_readings_dataframe()
    buf = visualization.generate_trend_chart(df)
    return send_file(buf, mimetype="image/png")

@app.route("/chart/consumer-comparison.png")
def chart_consumer_comparison():
    """
    Streams consumer comparison bar chart.
    """
    df = analysis.get_readings_dataframe()
    buf = visualization.generate_consumer_comparison_chart(df)
    return send_file(buf, mimetype="image/png")

@app.route("/chart/regional.png")
def chart_regional():
    """
    Streams regional distribution chart.
    """
    df = analysis.get_readings_dataframe()
    buf = visualization.generate_regional_breakdown_chart(df)
    return send_file(buf, mimetype="image/png")

# Legacy compatibility alias
@app.route("/chart.png")
def chart_legacy():
    return chart_trend()

# ----------------- Database Seeder Route -----------------

@app.route("/seed", methods=["POST"])
def seed_data_route():
    """
    Seeds comprehensive realistic records.
    """
    try:
        seeded = seed_sample_data()
        if seeded:
            flash("Sample data successfully loaded!", "success")
        else:
            flash("Database already contains data.", "info")
    except Exception as e:
        flash(f"Error seeding data: {e}", "error")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    print(f"Starting Electricity Consumption Analysis System on port {config.FLASK_PORT}...")
    app.run(
        host="0.0.0.0",
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )
