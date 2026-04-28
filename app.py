import os
import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Flask, jsonify, request
from mssql_python import connect

app = Flask(__name__)


def obtener_debug_resend():
    resend_api_key = os.getenv("RESEND_API_KEY")
    resend_from = os.getenv("RESEND_FROM")

    return {
        "RESEND_API_KEY_EXISTS": bool(resend_api_key),
        "RESEND_API_KEY_SUFFIX": resend_api_key[-4:] if resend_api_key else None,
        "RESEND_FROM": resend_from,
    }


def enviar_correo_alerta(asunto, mensaje, destino):
    resend_api_key = os.getenv("RESEND_API_KEY")
    resend_from = os.getenv("RESEND_FROM")

    if not resend_api_key:
        raise ValueError("Falta RESEND_API_KEY")
    if not resend_from:
        raise ValueError("Falta RESEND_FROM")

    payload = {
        "from": resend_from,
        "to": [destino],
        "subject": asunto,
        "text": mensaje,
    }

    req = urllib_request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib_request.urlopen(req, timeout=20) as response:
        if response.status not in (200, 202):
            raise ValueError(f"Resend respondió con estado {response.status}")

def get_connection():
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT", "1433")

    if not server:
        raise ValueError("Falta DB_SERVER")
    if not database:
        raise ValueError("Falta DB_DATABASE")
    if not username:
        raise ValueError("Falta DB_USERNAME")
    if not password:
        raise ValueError("Falta DB_PASSWORD")

    connection_string = (
        f"Server=tcp:{server},{port};"
        f"Database={database};"
        f"Uid={username};"
        f"Pwd={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Authentication=SqlPassword;"
    )

    return connect(connection_string)


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "API Flask funcionando correctamente en Render"
    })


@app.route("/debug-env")
def debug_env():
    return jsonify({
        "DB_SERVER": os.getenv("DB_SERVER"),
        "DB_DATABASE": os.getenv("DB_DATABASE"),
        "DB_USERNAME": os.getenv("DB_USERNAME"),
        "DB_PASSWORD_EXISTS": bool(os.getenv("DB_PASSWORD")),
        "DB_PORT": os.getenv("DB_PORT"),
    })


@app.route("/test-db")
def test_db():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT GETDATE() AS fecha_servidor")
        row = cursor.fetchone()

        return jsonify({
            "success": True,
            "message": "Conexión a SQL Server exitosa",
            "server_date": str(row[0])
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al conectar con SQL Server",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/productos")
def listar_productos():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 20 Id, Nombre, Precio, UrlImagen,Stock
            FROM Productos
            ORDER BY Id DESC
        """)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "nombre": row[1],
                "precio": float(row[2]) if row[2] is not None else None,
                "UrlImagen": row[3],
                "stock": row[4],
            })

        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al consultar productos",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route("/enviar-alerta", methods=["POST"]) 
def enviar_alerta():
    try:
        data = request.get_json(silent=True)
        debug_activo = request.args.get("debug") == "1"

        if not data:
            respuesta = {
                "success": False,
                "message": "El cuerpo debe ser JSON con to, subject y message"
            }
            if debug_activo:
                respuesta["debug"] = obtener_debug_resend()
            return jsonify(respuesta), 400

        destino = data.get("to")
        asunto = data.get("subject")
        mensaje = data.get("message")

        if not destino or not asunto or not mensaje:
            respuesta = {
                "success": False,
                "message": "Faltan datos"
            }
            if debug_activo:
                respuesta["debug"] = obtener_debug_resend()
            return jsonify(respuesta), 400

        enviar_correo_alerta(asunto, mensaje, destino)

        respuesta = {
            "success": True,
            "message": "Correo enviado"
        }
        if debug_activo:
            respuesta["debug"] = obtener_debug_resend()
        return jsonify(respuesta)

    except urllib_error.HTTPError as e:
        detalle = e.read().decode("utf-8", "ignore")
        respuesta = {
            "success": False,
            "message": "Error al enviar con Resend",
            "error": f"HTTP {e.code}: {detalle}"
        }
        if request.args.get("debug") == "1":
            respuesta["debug"] = obtener_debug_resend()
        return jsonify(respuesta), 502

    except urllib_error.URLError as e:
        respuesta = {
            "success": False,
            "message": "Error de red al conectar con Resend",
            "error": str(e)
        }
        if request.args.get("debug") == "1":
            respuesta["debug"] = obtener_debug_resend()
        return jsonify(respuesta), 503

    except Exception as e:
        respuesta = {
            "success": False,
            "message": "Error al enviar el correo",
            "error": str(e)
        }
        if request.args.get("debug") == "1":
            respuesta["debug"] = obtener_debug_resend()
        return jsonify(respuesta), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
