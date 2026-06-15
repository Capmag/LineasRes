from flask import Blueprint, request, render_template, jsonify
from utils import fetch_all, fetch_one, execute_query, execute_transaction, api_error, is_valid_email

empleados_bp = Blueprint('empleados', __name__)


@empleados_bp.route("/api/empleados", methods=["GET"])
def api_empleados():
    empleados = fetch_all("""
        SELECT id, CONCAT(nombre, ' ', COALESCE(apellido, '')) AS label
        FROM empleados
        WHERE estatus = 'Activo'
          AND id NOT IN (
              SELECT empleado_id FROM asignaciones
              WHERE estatus = 'Vigente' AND fecha_fin IS NULL
          )
        ORDER BY nombre, apellido
    """)
    return jsonify(empleados)


@empleados_bp.route("/empleados", methods=["GET"])
def lista_empleados():
    empleados = fetch_all("""
        SELECT
            e.id, e.nombre, e.apellido, e.correo, e.area_id, e.estatus,
            a.nombre AS area
        FROM empleados e
        LEFT JOIN areas a ON e.area_id = a.id
        ORDER BY e.nombre, e.apellido
        LIMIT 100
    """)
    return render_template("lista_empleados.html", empleados=empleados)


@empleados_bp.route("/empleado/baja/<id>", methods=["POST"])
def baja_empleado(id):
    try:
        asignacion = fetch_one("""
            SELECT id, linea_id, imei FROM asignaciones
            WHERE empleado_id = %s AND estatus = 'Vigente' AND fecha_fin IS NULL
        """, (id,))
        statements = [
            ("UPDATE empleados SET estatus = %s WHERE id = %s", ("Inactivo", id))
        ]
        if asignacion:
            statements += [
                ("UPDATE asignaciones SET estatus = 'Cerrada', fecha_fin = NOW() WHERE id = %s",
                 (asignacion["id"],)),
                ("UPDATE lineas SET estatus = 'Disponible' WHERE id = %s",
                 (asignacion["linea_id"],)),
                ("UPDATE equipos SET estatus = 'Disponible' WHERE imei = %s",
                 (asignacion["imei"],)),
                ("""INSERT INTO historial_asignaciones
                    (asignacion_id, empleado_id, linea_id, imei, fecha_inicio, fecha_fin, tipo_movimiento, motivo)
                    VALUES (%s, %s, %s, %s, NOW(), NOW(), 'Baja', 'Baja de empleado')""",
                 (asignacion["id"], id, asignacion["linea_id"], asignacion["imei"]))
            ]
        execute_transaction(statements)
        msg = "Empleado inactivado" + (" y asignación cerrada automáticamente" if asignacion else "")
        return jsonify({"ok": True, "msg": msg})
    except Exception as e:
        return api_error(e)


@empleados_bp.route("/empleado/reactivar/<id>", methods=["POST"])
def reactivar_empleado(id):
    try:
        execute_query("UPDATE empleados SET estatus = %s WHERE id = %s", ("Activo", id))
        return jsonify({"ok": True, "msg": "Empleado reactivado"})
    except Exception as e:
        return api_error(e)


@empleados_bp.route("/empleado/crear", methods=["GET", "POST"])
def crear_empleados():
    if request.method == "GET":
        areas = fetch_all("SELECT id, nombre FROM areas ORDER BY nombre")
        return render_template("crear_empleado.html", areas=areas)

    try:
        data = request.get_json(force=True)

        empleado_id = (data.get("id") or data.get("idEmpleado") or "").strip()
        nombre = (data.get("nombre") or data.get("nombreEmpleado") or "").strip()
        apellido = (data.get("apellido") or data.get("apellidoEmpleado") or "").strip()
        correo = (data.get("correo") or data.get("correoEmpleado") or "").strip()
        area_id = (data.get("area_id") or data.get("idArea") or "").strip()

        if not empleado_id:
            return jsonify({"ok": False, "msg": "El id del empleado es obligatorio"}), 400
        if not nombre:
            return jsonify({"ok": False, "msg": "El nombre del empleado es obligatorio"}), 400
        if not correo:
            return jsonify({"ok": False, "msg": "El correo del empleado es obligatorio"}), 400
        if not is_valid_email(correo):
            return jsonify({"ok": False, "msg": "El correo no tiene un formato válido"}), 400
        if not area_id:
            return jsonify({"ok": False, "msg": "El id del área es obligatorio"}), 400

        if not fetch_one("SELECT 1 FROM areas WHERE id = %s", (area_id,)):
            return jsonify({"ok": False, "msg": "El área no existe"}), 400

        execute_query("""
            INSERT INTO empleados (id, nombre, apellido, correo, area_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (empleado_id, nombre, apellido or None, correo, area_id))

        return jsonify({
            "ok": True,
            "msg": "Empleado creado correctamente",
            "redirect": "/empleados"
        }), 201

    except Exception as e:
        return api_error(e)


@empleados_bp.route("/empleado/editar/<id>", methods=["GET", "POST"])
def actualizar_empleados(id):
    if request.method == "GET":
        empleado = fetch_one("""
            SELECT id, nombre, apellido, correo, area_id
            FROM empleados WHERE id = %s
        """, (id,))
        if not empleado:
            return "Empleado no encontrado", 404
        return render_template("actualizar_empleado.html", empleado=empleado)

    try:
        data = request.get_json(force=True)

        nuevo_id = (data.get("nuevo_id") or "").strip()
        nuevo_nombre = (data.get("nuevo_nombre") or "").strip()
        nuevo_apellido = (data.get("nuevo_apellido") or "").strip()
        nuevo_correo = (data.get("nuevo_correo") or "").strip()
        nuevo_area = (data.get("nuevo_area") or "").strip()

        actual = fetch_one(
            "SELECT id, nombre, apellido, correo, area_id FROM empleados WHERE id = %s", (id,)
        )
        if not actual:
            return jsonify({"ok": False, "msg": "Empleado no encontrado"}), 404

        if not nuevo_id:
            nuevo_id = actual["id"]
        if not nuevo_nombre:
            nuevo_nombre = actual["nombre"]
        if not nuevo_apellido:
            nuevo_apellido = actual["apellido"]
        if not nuevo_correo:
            nuevo_correo = actual["correo"]

        if not is_valid_email(nuevo_correo):
            return jsonify({"ok": False, "msg": "El correo no tiene un formato válido"}), 400

        if not nuevo_area:
            nuevo_area = actual["area_id"]

        if not fetch_one("SELECT 1 FROM areas WHERE id = %s", (nuevo_area,)):
            return jsonify({"ok": False, "msg": "El área no existe"}), 400

        execute_query("""
            UPDATE empleados
            SET id = %s, nombre = %s, apellido = %s, correo = %s, area_id = %s
            WHERE id = %s
        """, (nuevo_id, nuevo_nombre, nuevo_apellido, nuevo_correo, nuevo_area, id))

        return jsonify({"ok": True, "msg": "Empleado actualizado correctamente"})

    except Exception as e:
        return api_error(e)
