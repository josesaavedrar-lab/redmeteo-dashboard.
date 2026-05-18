from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ================= REDMETEO =================
REDMETEO_URL = "https://redmeteo.cl/last-data.json"
ESTACION_OBJETIVO = "Valparaíso - Capitanía de Puerto (SERVIMET)"

# ================= FIREBASE =================
FIREBASE_BASE = "https://esp32pucv220426-default-rtdb.firebaseio.com"


def numero(valor):
    try:
        return float(valor)
    except:
        return None


def elegir_valor(*valores):
    for valor in valores:
        n = numero(valor)
        if n is not None:
            return n
    return None


def obtener_redmeteo():
    response = requests.get(REDMETEO_URL, timeout=10)
    data = response.json()

    for e in data:
        if ESTACION_OBJETIVO in e.get("nombre", ""):
            return {
                "fuente": "RedMeteo",
                "estacion": e.get("nombre"),
                "fecha": e.get("fecha_hora") or e.get("fecha"),
                "temperatura": elegir_valor(e.get("temperatura")),
                "humedad": elegir_valor(e.get("humedad")),
                "presion": elegir_valor(e.get("presion")),
                "irradiacion": elegir_valor(
                    e.get("radiacion_solar"),
                    e.get("irradiacion"),
                    e.get("radiacion")
                ),
                "estado": "Online"
            }
    return None


def obtener_panel_jose():
    url = f"{FIREBASE_BASE}/jose/datos.json"
    response = requests.get(url, timeout=5)
    data = response.json()

    if data is None:
        return {
            "fuente": "Panel José",
            "temperatura": None,
            "voltaje": None,
            "corriente": None,
            "irradiacion": None,
            "estado": "Sin datos"
        }

    timestamp = numero(data.get("timestamp"))
    ahora = datetime.now().timestamp()

    if timestamp is not None and (ahora - timestamp) <= 120:
        estado = "Online"
    else:
        estado = "Offline"

    return {
        "fuente": "Panel José",
        "temperatura": numero(data.get("temperatura")),
        "voltaje": numero(data.get("voltaje")),
        "corriente": numero(data.get("corriente")),
        "irradiacion": None,
        "timestamp": data.get("timestamp"),
        "estado": estado
    }


def obtener_panel_mauricio(redmeteo):
    temp_base = redmeteo["temperatura"] or 20
    irr_base = redmeteo["irradiacion"] if redmeteo["irradiacion"] is not None else 0

    return {
        "fuente": "Panel Mauricio",
        "temperatura": round(temp_base + random.uniform(-2, 2), 1),
        "voltaje": round(random.uniform(11.0, 13.8), 2),
        "corriente": round(random.uniform(0.2, 1.4), 2),
        "irradiacion": round(max(0, irr_base + random.uniform(-50, 50)), 1),
        "estado": "Simulado"
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def api_dashboard():
    try:
        redmeteo = obtener_redmeteo()

        if redmeteo is None:
            return jsonify({
                "ok": False,
                "error": "No se encontró la estación RedMeteo"
            })

        panel_jose = obtener_panel_jose()
        panel_mauricio = obtener_panel_mauricio(redmeteo)

        return jsonify({
            "ok": True,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "redmeteo_fecha": redmeteo["fecha"],
            "data": [
                panel_jose,
                panel_mauricio,
                redmeteo
            ]
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        })


if __name__ == "__main__":
    app.run(debug=True, port=3000)