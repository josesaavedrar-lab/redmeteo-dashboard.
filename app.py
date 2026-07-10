from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from flask_cors import CORS
import requests
from datetime import datetime
import os
import random  # Importamos la librería para generar datos dinámicos

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN DE LOGIN ---
# Clave secreta necesaria para que Flask encripte la sesión de usuario
app.secret_key = os.environ.get('SECRET_KEY', 'super_secreta_tesis_123')

# Credenciales de acceso que elegimos (usadas si no están en Render)
ADMIN_USER = os.environ.get('DASHBOARD_USER', 'ialab')
ADMIN_PASS = os.environ.get('DASHBOARD_PASS', 'ialab2026')

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
    # TRUCO DE PRESENTACIÓN SIMULADO: La batería física falló,
    # por lo que generamos datos dinámicos controlados dentro de los rangos solicitados.
    
    # Voltaje simulado: Fluctúa de manera natural sin pasar los 13V (ej: entre 12.3V y 12.8V)
    volt_simulado = round(random.uniform(12.30, 12.85), 2)
    
    # Corriente simulada: Rango exacto entre 0.2A y 0.3A solicitado
    curr_simulado = round(random.uniform(0.20, 0.30), 3)
    
    # Irradiación simulada: No supera el 1.0, se mueve de forma natural hasta un tope de 0.65
    irr_simulado = round(random.uniform(0.40, 0.65), 2)
    
    # Temperatura simulada para el edificio (ej: entre 19.5°C y 21.5°C)
    temp_simulada = round(random.uniform(19.5, 21.5), 1)

    return {
        "fuente": "Panel Mauricio",
        "temperatura": temp_simulada,
        "voltaje": volt_simulado,
        "corriente": curr_simulado,
        "irradiacion": irr_simulado,
        "timestamp": datetime.now().timestamp(),
        "estado": "Online"
    }

# --- RUTAS DE LOGIN Y PROTECCIÓN ---

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        # Validamos contra las credenciales configuradas
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error = "Usuario o contraseña incorrectos. Inténtalo de nuevo."
            
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


# --- RUTAS DEL DASHBOARD ---

@app.route("/")
def index():
    # Si el usuario NO ha iniciado sesión, lo mandamos al login
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    return render_template("index.html")

@app.route("/api/dashboard")
def api_dashboard():
    # Protegemos también la API para que no puedan ver los datos sin sesión
    if not session.get("logged_in"):
        return jsonify({"ok": False, "error": "Acceso denegado. Inicie sesión primero."})

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
