from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import io
import json

app = Flask(__name__)

SAMPLE_DATA = [
    {"month": "Jan", "year": 2023, "temperature": 12.0, "rainfall": 18.0},
    {"month": "Feb", "year": 2023, "temperature": 14.0, "rainfall": 22.0},
    {"month": "Mar", "year": 2023, "temperature": 18.0, "rainfall": 35.0},
    {"month": "Apr", "year": 2023, "temperature": 24.0, "rainfall": 28.0},
    {"month": "May", "year": 2023, "temperature": 31.0, "rainfall": 42.0},
    {"month": "Jun", "year": 2023, "temperature": 38.0, "rainfall": 85.0},
    {"month": "Jul", "year": 2023, "temperature": 36.0, "rainfall": 210.0},
    {"month": "Aug", "year": 2023, "temperature": 34.0, "rainfall": 195.0},
    {"month": "Sep", "year": 2023, "temperature": 34.0, "rainfall": 120.0},
    {"month": "Oct", "year": 2023, "temperature": 27.0, "rainfall": 55.0},
    {"month": "Nov", "year": 2023, "temperature": 19.0, "rainfall": 20.0},
    {"month": "Dec", "year": 2023, "temperature": 13.0, "rainfall": 14.0},
    {"month": "Jan", "year": 2024, "temperature": 22.0, "rainfall": 18.0},
    {"month": "Feb", "year": 2024, "temperature": 14.0, "rainfall": 62.0},
    {"month": "Mar", "year": 2024, "temperature": 19.0, "rainfall": 36.0},
    {"month": "Apr", "year": 2024, "temperature": 31.0, "rainfall": 29.0},
    {"month": "May", "year": 2024, "temperature": 30.0, "rainfall": 41.0},
    {"month": "Jun", "year": 2024, "temperature": 42.0, "rainfall": 90.0},
    {"month": "Jul", "year": 2024, "temperature": 35.0, "rainfall": 250.0},
    {"month": "Aug", "year": 2024, "temperature": 33.0, "rainfall": 188.0},
    {"month": "Sep", "year": 2024, "temperature": 33.0, "rainfall": 115.0},
    {"month": "Oct", "year": 2024, "temperature": 26.0, "rainfall": 52.0},
    {"month": "Nov", "year": 2024, "temperature": 20.0, "rainfall": 22.0},
    {"month": "Dec", "year": 2024, "temperature": 12.0, "rainfall": 12.0},
]

SEASON_MAP = {
    "Dec": "Winter", "Jan": "Winter", "Feb": "Winter",
    "Mar": "Spring", "Apr": "Spring", "May": "Spring",
    "Jun": "Summer", "Jul": "Summer", "Aug": "Summer",
    "Sep": "Autumn", "Oct": "Autumn", "Nov": "Autumn"
}

def detect_anomalies(df, temp_thresh, rain_thresh, mode):
    df = df.copy()
    df["season"] = df["month"].map(SEASON_MAP)
    group_key = "season" if mode == "seasonal" else "month"

    # Calculate averages using pandas groupby
    avg = df.groupby(group_key)[["temperature", "rainfall"]].mean().rename(
        columns={"temperature": "avg_temp", "rainfall": "avg_rain"}
    )
    df = df.join(avg, on=group_key)

    # Differences
    df["temp_diff"] = df["temperature"] - df["avg_temp"]
    df["rain_diff"] = df["rainfall"] - df["avg_rain"]

    # Flag anomalies
    df["is_anomaly"] = (
        (df["temp_diff"].abs() > temp_thresh) |
        (df["rain_diff"].abs() > rain_thresh)
    )

    # Stats
    stats = {
        "total": int(len(df)),
        "anomalies": int(df["is_anomaly"].sum()),
        "avg_temp": round(float(df["temperature"].mean()), 2),
        "avg_rain": round(float(df["rainfall"].mean()), 2),
        "max_temp": round(float(df["temperature"].max()), 2),
        "min_temp": round(float(df["temperature"].min()), 2),
        "max_rain": round(float(df["rainfall"].max()), 2),
        "anomaly_pct": round(float(df["is_anomaly"].mean()) * 100, 1),
    }

    # Records for table/chart
    records = []
    for i, row in df.iterrows():
        records.append({
            "idx": i + 1,
            "month": row["month"],
            "year": int(row["year"]) if "year" in df.columns else "",
            "temperature": round(float(row["temperature"]), 1),
            "rainfall": round(float(row["rainfall"]), 1),
            "avg_temp": round(float(row["avg_temp"]), 1),
            "avg_rain": round(float(row["avg_rain"]), 1),
            "temp_diff": round(float(row["temp_diff"]), 1),
            "rain_diff": round(float(row["rain_diff"]), 1),
            "is_anomaly": bool(row["is_anomaly"]),
        })

    return stats, records


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/sample", methods=["GET"])
def use_sample():
    temp_thresh = float(request.args.get("temp_thresh", 3))
    rain_thresh = float(request.args.get("rain_thresh", 20))
    mode = request.args.get("mode", "monthly")

    df = pd.DataFrame(SAMPLE_DATA)
    stats, records = detect_anomalies(df, temp_thresh, rain_thresh, mode)
    return jsonify({"ok": True, "stats": stats, "records": records})


@app.route("/api/upload", methods=["POST"])
def upload_csv():
    try:
        temp_thresh = float(request.form.get("temp_thresh", 3))
        rain_thresh = float(request.form.get("rain_thresh", 20))
        mode = request.form.get("mode", "monthly")

        file = request.files.get("file")
        if not file:
            return jsonify({"ok": False, "error": "No file uploaded"}), 400

        content = file.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(content))
        df.columns = [c.strip().lower() for c in df.columns]

        required = {"month", "temperature", "rainfall"}
        if not required.issubset(set(df.columns)):
            missing = required - set(df.columns)
            return jsonify({"ok": False, "error": f"Missing columns: {', '.join(missing)}"}), 400

        df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
        df["rainfall"] = pd.to_numeric(df["rainfall"], errors="coerce")
        df = df.dropna(subset=["temperature", "rainfall"])

        if len(df) == 0:
            return jsonify({"ok": False, "error": "No valid rows found in CSV"}), 400

        stats, records = detect_anomalies(df, temp_thresh, rain_thresh, mode)
        return jsonify({"ok": True, "stats": stats, "records": records})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
