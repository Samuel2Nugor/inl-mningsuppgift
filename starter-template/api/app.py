import os
import time
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
import yaml

app = Flask(__name__)

# Konfiguration från miljövariabler
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'telemetry_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASS', 'postgres')

def get_db_connection():
    """Skapar anslutning till databasen med retry-logik."""
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            print("Väntar på databasanslutning...")
            time.sleep(2)
    raise Exception("Kunde inte ansluta till databasen")

def init_db():
    """Initierar databasschema om det inte existerar."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id SERIAL PRIMARY KEY,
                sensor_id VARCHAR(100) NOT NULL,
                metric_type VARCHAR(50) NOT NULL,
                value NUMERIC NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Databasschema initierat.")
    except Exception as e:
        print(f"Fel vid databasinitiering: {e}")

@app.route('/health', methods=['GET'])
def health():
    """Hälsoändpunkt för container och orkestrering."""
    return jsonify({"status": "healthy"}), 200

@app.route('/openapi.json', methods=['GET'])
def get_openapi():
    """Exponerar OpenAPI-kontraktet i JSON-format för Schemathesis."""
    openapi_path = os.path.join(os.path.dirname(__file__), 'openapi.yaml')
    if os.path.exists(openapi_path):
        with open(openapi_path, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
        return jsonify(spec), 200
    return jsonify({"error": "OpenAPI spec hittades inte"}), 404

@app.route('/api/v1/telemetry', methods=['GET'])
def get_telemetry():
    """Hämtar all registrerad telemetridata."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, sensor_id, metric_type, value, timestamp FROM telemetry ORDER BY id DESC;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        # Konvertera datetime till ISO-sträng
        for row in rows:
            if isinstance(row['timestamp'], datetime):
                row['timestamp'] = row['timestamp'].isoformat()
            row['value'] = float(row['value'])
            
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/telemetry', methods=['POST'])
def post_telemetry():
    """Sparar ny telemetridata från en sensor."""
    data = request.get_json()
    
    if not isinstance(data, dict):
        return jsonify({"error": "Ingen JSON-payload angiven"}), 400
        
    sensor_id = data.get('sensor_id')
    metric_type = data.get('metric_type')
    value = data.get('value')
    ts = data.get('timestamp')
    
    if not sensor_id or not metric_type or value is None:
        return jsonify({"error": "Obligatoriska fält saknas (sensor_id, metric_type, value)"}), 400
    
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return jsonify({"error": "Value måste vara ett numeriskt värde"}), 400

    if not isinstance(sensor_id, str) or not isinstance(metric_type, str):
        return jsonify({"error": "sensor_id or metric_type måste vara strängar"}), 400

    if 'timestamp' in data and data ['timestamp'] is not None:
        ts = data['timestamp']
        if not isinstance(ts, str):
            return jsonify({"error":"timestamp måste vara en sträng"}), 400
        
        try:
            parsed = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            offset = parsed.utcoffset()

            if offset is not None and abs(parsed.utcoffset().total_seconds()) > 15 * 3600 + 59 * 60:
                raise ValueError("offset out of range")
        except ValueError:
            return jsonify({"error": "timestamp har ogiltigt format"}), 400

    elif 'timestamp' in data and data['timestamp'] is None:
        return jsonify({"error": "timestamp får inte vara null"}), 400
    else:
        ts = None
         
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if ts:
            cur.execute(
                "INSERT INTO telemetry (sensor_id, metric_type, value, timestamp) VALUES (%s, %s, %s, %s);",
                (sensor_id, metric_type, value, ts)
            )
        else:
            cur.execute(
                "INSERT INTO telemetry (sensor_id, metric_type, value) VALUES (%s, %s, %s);",
                (sensor_id, metric_type, value)
            )
            
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Telemetry data created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
