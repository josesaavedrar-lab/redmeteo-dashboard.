from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# ================= REDMETEO =================
REDMETEO_URL = "https://redmeteo.cl/last-data.json"
ESTACION_OBJETIVO = "Valparaíso - Capitanía de Puerto (SERVIMET)"

# ================= FIREBASE =================
FIREBASE_BASE = "https://esp32pucv15062026-default-rtdb.firebaseio.com"

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
    try:
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
                    "irradiacion": elegir_valor(e.get("radiacion_solar"), e.get("irradiacion"), e.get("radiacion")),
                    "estado": "Online"
                }
    except:
        pass
    return None

def obtener_panel_jose():
    url = f"{FIREBASE_BASE}/jose/datos.json"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
    except:
        data = None

    if not data:
        return {"fuente": "Panel José", "temperatura": None, "voltaje": None, "corriente": None, "irradiacion": None, "estado": "Sin datos"}

    timestamp = numero(data.get("timestamp"))
    ahora = datetime.now().timestamp()
    estado = "Online" if timestamp is not None and (ahora - timestamp) <= 120 else "Offline"

    t1, t2, t3 = numero(data.get("temperatura_1")), numero(data.get("temperatura_2")), numero(data.get("temperatura_3"))
    temps_validas = [t for t in (t1, t2, t3) if t is not None]
    temp_promedio = round(sum(temps_validas) / len(temps_validas), 2) if temps_validas else None

    return {
        "fuente": "Panel José",
        "temperatura": temp_promedio,
        "voltaje": numero(data.get("voltaje")),
        "corriente": numero(data.get("corriente")),
        "irradiacion": numero(data.get("irradiancia_v")),
        "timestamp": data.get("timestamp"),
        "estado": estado
    }

def obtener_panel_mauricio():
    url = f"{FIREBASE_BASE}/mediciones.json"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
    except:
        data = None

    if not data:
        return {"fuente": "Panel Mauricio", "temperatura": None, "voltaje": None, "corriente": None, "irradiacion": None, "estado": "Sin datos"}

    # Detectar el nuevo formato de Mauricio (lista de timestamps)
    if isinstance(data, dict):
        if "datos" in data:
            ultimo = data["datos"]
        else:
            claves = sorted(data.keys())
            ultimo = data[claves[-1]]
    else:
        ultimo = data

    # Traducir los nuevos nombres de Mauricio (volt, curr, Irr, temp1...)
    t1, t2, t3 = numero(ultimo.get("temp1")), numero(ultimo.get("temp2")), numero(ultimo.get("temp3"))
    temps_validas = [t for t in (t1, t2, t3) if t is not None]
    temp_promedio = round(sum(temps_validas) / len(temps_validas), 2) if temps_validas else numero(ultimo.get("temperatura"))

    volt = numero(ultimo.get("volt")) or numero(ultimo.get("voltaje"))
    curr = numero(ultimo.get("curr")) or numero(ultimo.get("corriente"))
    irr = numero(ultimo.get("Irr")) or numero(ultimo.get("irradiacion"))

    # Si hay CUALQUIER dato de estos, forzar Online
    estado = "Online" if (temp_promedio is not None or volt is not None or curr is not None) else "Offline"

    return {
        "fuente": "Panel Mauricio",
        "temperatura": temp_promedio,
        "voltaje": volt,
        "corriente": curr,
        "irradiacion": irr,
        "timestamp": ultimo.get("ts") or ultimo.get("timestamp"),
        "estado": estado
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/dashboard")
def api_dashboard():
    try:
        redmeteo = obtener_redmeteo()
        if redmeteo is None:
            return jsonify({"ok": False, "error": "No se encontró la estación RedMeteo"})

        panel_jose = obtener_panel_jose()
        panel_mauricio = obtener_panel_mauricio()

        return jsonify({
            "ok": True,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "redmeteo_fecha": redmeteo["fecha"],
            "data": [panel_jose, panel_mauricio, redmeteo]
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=puerto, debug=False)
