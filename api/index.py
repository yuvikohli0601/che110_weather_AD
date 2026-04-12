from flask import Flask, request, jsonify, render_template
import pandas as pd
import io
import json

app = Flask(
    __name__,
    template_folder='../templates',
    static_folder='../static'
)

SAMPLE_DATA = [
    {"month": "Jan", "year": 2023, "temperature": 12.0, "rainfall": 18.0},
    {"month": "Feb", "year": 2023, "temperature": 14.0, "rainfall": 22.0},
    {"month": "Mar", "year": 2023, "temperature": 18.5, "rainfall": 35.0},
    {"month": "Apr", "year": 2023, "temperature": 24.0, "rainfall": 28.0},
    {"month": "May", "year": 2023, "temperature": 31.0, "rainfall": 42.0},
    {"month": "Jun", "year": 2023, "temperature": 38.0, "rainfall": 85.0},
    {"month": "Jul", "year": 2023, "temperature": 36.0, "rainfall": 210.0},
    {"month": "Aug", "year": 2023, "temperature": 34.5, "rainfall": 195.0},
    {"month": "Sep", "year": 2023, "temperature": 34.0, "rainfall": 120.0},
    {"month": "Oct", "year": 2023, "temperature": 27.0, "rainfall": 55.0},
    {"month": "Nov", "year": 2023, "temperature": 19.0, "rainfall": 20.0},
    {"month": "Dec", "year": 2023, "temperature": 13.0, "rainfall": 14.0},
    {"month": "Jan", "year": 2024, "temperature": 22.0, "rainfall": 18.0},  # anomaly - hot Jan
    {"month": "Feb", "year": 2024, "temperature": 14.2, "rainfall": 62.0},  # anomaly - heavy rain
    {"month": "Mar", "year": 2024, "temperature": 19.0, "rainfall": 36.0},
    {"month": "Apr", "year": 2024, "temperature": 31.0, "rainfall": 29.0},  # anomaly - hot Apr
    {"month": "May", "year": 2024, "temperature": 30.5, "rainfall": 41.0},
    {"month": "Jun", "year": 2024, "temperature": 42.0, "rainfall": 90.0},  # anomaly - extreme heat
    {"month": "Jul", "year": 2024, "temperature": 35.0, "rainfall": 250.0}, # anomaly - heavy rain
    {"month": "Aug", "year": 2024, "temperature": 33.0, "rainfall": 188.0},
    {"month": "Sep", "year": 2024, "temperature": 33.0, "rainfall": 115.0},
    {"month": "Oct", "year": 2024, "temperature": 26.0, "rainfall": 52.0},
    {"month": "Nov", "year": 2024, "temperature": 20.0, "rainfall": 22.0},
    {"month": "Dec", "year": 2024, "temperature": 12.0, "rainfall": 12.0},
]

SEASON_MAP = {
    'jan': 'Winter', 'feb': 'Winter', 'dec': 'Winter',
    'mar': 'Spring', 'apr': 'Spring', 'may': 'Spring',
    'jun': 'Summer', 'jul': 'Summer', 'aug': 'Summer',
    'sep': 'Autumn', 'oct': 'Autumn', 'nov': 'Autumn',
}

def detect_anomalies(records, temp_thresh, rain_thresh, mode):
    df = pd.DataFrame(records)

    if mode == 'seasonal':
        df['group'] = df['month'].str.lower().str[:3].map(SEASON_MAP)
    else:
        df['group'] = df['month'].str[:3]

    # Calculate group averages
    avg = df.groupby('group')[['temperature', 'rainfall']].mean().to_dict()

    results = []
    for _, row in df.iterrows():
        g = row['group']
        avg_temp = avg['temperature'][g]
        avg_rain = avg['rainfall'][g]
        temp_diff = round(row['temperature'] - avg_temp, 2)
        rain_diff = round(row['rainfall'] - avg_rain, 2)
        is_anomaly = abs(temp_diff) > temp_thresh or abs(rain_diff) > rain_thresh

        reasons = []
        if abs(temp_diff) > temp_thresh:
            direction = "above" if temp_diff > 0 else "below"
            reasons.append(f"Temp {abs(temp_diff):.1f}°C {direction} average")
        if abs(rain_diff) > rain_thresh:
            direction = "above" if rain_diff > 0 else "below"
            reasons.append(f"Rainfall {abs(rain_diff):.1f}mm {direction} average")

        results.append({
            "month": row['month'],
            "year": int(row['year']) if 'year' in row else None,
            "temperature": round(float(row['temperature']), 1),
            "rainfall": round(float(row['rainfall']), 1),
            "avg_temp": round(avg_temp, 1),
            "avg_rain": round(avg_rain, 1),
            "temp_diff": temp_diff,
            "rain_diff": rain_diff,
            "is_anomaly": bool(is_anomaly),
            "group": g,
            "reasons": reasons
        })

    total = len(results)
    anomaly_count = sum(1 for r in results if r['is_anomaly'])
    overall_avg_temp = round(df['temperature'].mean(), 1)
    overall_avg_rain = round(df['rainfall'].mean(), 1)
    max_temp = round(df['temperature'].max(), 1)
    min_temp = round(df['temperature'].min(), 1)

    return {
        "results": results,
        "summary": {
            "total": total,
            "anomalies": anomaly_count,
            "anomaly_pct": round((anomaly_count / total) * 100, 1),
            "avg_temp": overall_avg_temp,
            "avg_rain": overall_avg_rain,
            "max_temp": max_temp,
            "min_temp": min_temp,
        }
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/sample', methods=['GET'])
def get_sample():
    return jsonify({"data": SAMPLE_DATA})


@app.route('/api/detect', methods=['POST'])
def detect():
    try:
        temp_thresh = float(request.form.get('temp_thresh', 3))
        rain_thresh = float(request.form.get('rain_thresh', 20))
        mode = request.form.get('mode', 'monthly')
        source = request.form.get('source', 'sample')

        if source == 'sample':
            records = SAMPLE_DATA
        else:
            file = request.files.get('file')
            if not file:
                return jsonify({"error": "No file uploaded"}), 400

            content = file.read().decode('utf-8')
            df = pd.read_csv(io.StringIO(content))
            df.columns = [c.strip().lower() for c in df.columns]

            required = {'month', 'temperature', 'rainfall'}
            if not required.issubset(set(df.columns)):
                return jsonify({"error": f"CSV must have columns: month, temperature, rainfall. Found: {list(df.columns)}"}), 400

            if 'year' not in df.columns:
                df['year'] = 2024

            df = df.dropna(subset=['temperature', 'rainfall'])
            records = df.to_dict('records')

        result = detect_anomalies(records, temp_thresh, rain_thresh, mode)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
