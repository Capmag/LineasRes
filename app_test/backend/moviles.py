from flask import Blueprint, request, render_template, jsonify
from utils import fetch_all, fetch_one, execute_query, api_error

moviles_bp = Blueprint('moviles', __name__)


@moviles_bp.route("/api/moviles", methods=["GET"])
def api_moviles():
    moviles = fetch_all("""
        SELECT imei AS id, COALESCE(modelo, imei) AS label
        FROM equipos
        WHERE estatus IN ('Disponible', 'Asignado')
        ORDER BY modelo, imei
    """)
    return jsonify(moviles)


@moviles_bp.route("/moviles", methods=["GET", "POST"])
def lista_moviles():
    if request.method == "GET":
        moviles = fetch_all("""
            SELECT
                eq.imei,
                eq.marca,
                eq.modelo,
                eq.serial,
                eq.estatus,
                eq.motivo_no_disponible,
                IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS linea,
                CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
                a.fecha_inicio,
                a.fecha_fin
            FROM equipos eq
            LEFT JOIN asignaciones a ON a.imei = eq.imei
                AND a.estatus = 'Vigente' AND a.fecha_fin IS NULL
            LEFT JOIN lineas l ON l.id = a.linea_id
            LEFT JOIN empleados e ON e.id = a.empleado_id
            ORDER BY eq.imei
            LIMIT 100
        """)
        return render_template("lista_moviles.html", moviles=moviles)

    try:
        data = request.get_json(force=True)
        movil_imei = data.get("imei") or data.get("id")

        active_assignment = fetch_one("""
            SELECT id FROM asignaciones
            WHERE imei = %s AND estatus = 'Vigente' AND fecha_fin IS NULL
        """, (movil_imei,))

        if active_assignment:
            return jsonify({
                "ok": False,
                "msg": "No se puede eliminar un equipo con asignación vigente. Ciérrela primero."
            }), 400

        execute_query("UPDATE equipos SET estatus = 'Baja' WHERE imei = %s", (movil_imei,))
        return jsonify({"ok": True, "msg": "Equipo marcado como baja correctamente"})

    except Exception as e:
        return api_error(e)


@moviles_bp.route("/movil/crear", methods=["POST"])
def crear_moviles():
    try:
        data = request.get_json(force=True)

        imei = (data.get("imei") or "").strip()
        marca = (data.get("marca") or "").strip() or None
        modelo = (data.get("modelo") or "").strip() or None
        serial = (data.get("serial") or "").strip() or None

        if not imei:
            return jsonify({"ok": False, "msg": "El IMEI del equipo es obligatorio"}), 400
        if not imei.isdigit():
            return jsonify({"ok": False, "msg": "El IMEI debe contener solo números"}), 400
        if len(imei) != 15:
            return jsonify({"ok": False, "msg": "El IMEI debe tener exactamente 15 dígitos"}), 400

        if fetch_one("SELECT 1 FROM equipos WHERE imei = %s", (imei,)):
            return jsonify({"ok": False, "msg": "Ya existe un equipo con este IMEI"}), 400

        execute_query("""
            INSERT INTO equipos (imei, marca, modelo, serial, estatus)
            VALUES (%s, %s, %s, %s, 'Disponible')
        """, (imei, marca, modelo, serial))

        return jsonify({"ok": True, "msg": "Equipo creado correctamente", "redirect": "/moviles"}), 201

    except Exception as e:
        return api_error(e)


@moviles_bp.route("/movil/editar/<id>", methods=["POST"])
def actualizar_moviles(id):
    try:
        data = request.get_json(force=True)

        actual = fetch_one(
            "SELECT imei, marca, modelo, serial, estatus FROM equipos WHERE imei = %s",
            (id,)
        )
        if not actual:
            return jsonify({"ok": False, "msg": "Equipo no encontrado"}), 404

        nuevo_imei = (data.get("imei") or "").strip() or actual["imei"]
        nueva_marca = ((data.get("marca") or "").strip() or None) if "marca" in data else actual["marca"]
        nuevo_modelo = ((data.get("modelo") or "").strip() or None) if "modelo" in data else actual["modelo"]
        nuevo_serial = ((data.get("serial") or "").strip() or None) if "serial" in data else actual["serial"]

        execute_query("""
            UPDATE equipos
            SET imei = %s, marca = %s, modelo = %s, serial = %s
            WHERE imei = %s
        """, (nuevo_imei, nueva_marca, nuevo_modelo, nuevo_serial, id))

        return jsonify({"ok": True, "msg": "Equipo actualizado correctamente"})

    except Exception as e:
        return api_error(e)
