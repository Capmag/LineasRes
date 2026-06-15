from flask import Blueprint, request, render_template, jsonify
from utils import fetch_all, fetch_one, execute_query, execute_transaction, api_error
import uuid

asignaciones_bp = Blueprint('asignaciones', __name__)


@asignaciones_bp.route("/asignaciones", methods=["GET"])
def lista_asignaciones():
    estatus = request.args.get('estatus', 'Vigente')

    query = """
        SELECT
            asi.id,
            asi.fecha_inicio,
            asi.fecha_fin,
            asi.estatus,
            asi.observaciones,
            CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
            IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS linea,
            eq.imei,
            eq.modelo,
            ar.nombre AS area
        FROM asignaciones asi
        JOIN empleados e ON e.id = asi.empleado_id
        JOIN lineas l ON l.id = asi.linea_id
        JOIN equipos eq ON eq.imei = asi.imei
        JOIN areas ar ON ar.id = e.area_id
        WHERE asi.estatus = %s
    """

    if estatus == 'Vigente':
        query += " AND asi.fecha_fin IS NULL"

    query += " ORDER BY asi.fecha_inicio DESC LIMIT 200"

    asignaciones = fetch_all(query, (estatus,))
    return render_template("lista_asignaciones.html", asignaciones=asignaciones, estatus=estatus)


@asignaciones_bp.route("/asignar", methods=["GET", "POST"])
def crear_asignacion():
    if request.method == "GET":
        empleados = fetch_all("SELECT id, nombre FROM empleados WHERE estatus = 'Activo' ORDER BY nombre")
        return render_template("crear_asignacion.html", empleados=empleados)

    try:
        data = request.get_json(force=True)

        empleado_id = (data.get("empleado_id") or "").strip()
        linea_id = (data.get("linea_id") or "").strip()
        imei = (data.get("imei") or "").strip()
        observaciones = (data.get("observaciones") or "").strip() or None

        if not empleado_id or not linea_id or not imei:
            return jsonify({"ok": False, "msg": "Empleado, línea e IMEI son obligatorios"}), 400

        if not fetch_one("SELECT 1 FROM empleados WHERE id = %s AND estatus = 'Activo'", (empleado_id,)):
            return jsonify({"ok": False, "msg": "El empleado no existe o está inactivo"}), 400

        linea = fetch_one("SELECT id, estatus FROM lineas WHERE id = %s", (linea_id,))
        if not linea:
            return jsonify({"ok": False, "msg": "La línea no existe"}), 400
        if linea["estatus"] != 'Disponible':
            return jsonify({"ok": False, "msg": f"La línea no está disponible (estado: {linea['estatus']})"}), 400

        equipo = fetch_one("SELECT imei, estatus FROM equipos WHERE imei = %s", (imei,))
        if not equipo:
            return jsonify({"ok": False, "msg": "El equipo no existe"}), 400
        if equipo["estatus"] != 'Disponible':
            return jsonify({"ok": False, "msg": f"El equipo no está disponible (estado: {equipo['estatus']})"}), 400

        existing_assignment = fetch_one("""
            SELECT id FROM asignaciones
            WHERE empleado_id = %s AND linea_id = %s AND estatus = 'Vigente' AND fecha_fin IS NULL
        """, (empleado_id, linea_id))

        if existing_assignment:
            return jsonify({"ok": False, "msg": "Este empleado ya tiene asignada esta línea"}), 400

        asignacion_id = str(uuid.uuid4())

        execute_transaction([
            ("""
                INSERT INTO asignaciones (id, empleado_id, linea_id, imei, fecha_inicio, estatus, observaciones)
                VALUES (%s, %s, %s, %s, NOW(), 'Vigente', %s)
            """, (asignacion_id, empleado_id, linea_id, imei, observaciones)),
            ("""
                UPDATE lineas SET estatus = 'Asignado' WHERE id = %s
            """, (linea_id,)),
            ("""
                UPDATE equipos SET estatus = 'Asignado' WHERE imei = %s
            """, (imei,)),
            ("""
                INSERT INTO historial_asignaciones
                (asignacion_id, empleado_id, linea_id, imei, fecha_inicio, tipo_movimiento, motivo)
                VALUES (%s, %s, %s, %s, NOW(), 'Alta', %s)
            """, (asignacion_id, empleado_id, linea_id, imei, observaciones))
        ])

        return jsonify({"ok": True, "msg": "Asignación creada correctamente", "redirect": "/asignaciones"}), 201

    except Exception as e:
        return api_error(e)


@asignaciones_bp.route("/asignacion/<id>/baja", methods=["POST"])
def cerrar_asignacion(id):
    try:
        data = request.get_json(force=True)
        motivo = (data.get("motivo") or "").strip() or "Sin motivo"

        asignacion = fetch_one("""
            SELECT id, empleado_id, linea_id, imei FROM asignaciones
            WHERE id = %s AND estatus = 'Vigente'
        """, (id,))

        if not asignacion:
            return jsonify({"ok": False, "msg": "Asignación no encontrada o ya está cerrada"}), 404

        execute_transaction([
            ("""
                UPDATE asignaciones SET estatus = 'Cerrada', fecha_fin = NOW() WHERE id = %s
            """, (id,)),
            ("""
                UPDATE lineas SET estatus = 'Disponible' WHERE id = %s
            """, (asignacion["linea_id"],)),
            ("""
                UPDATE equipos SET estatus = 'Disponible' WHERE imei = %s
            """, (asignacion["imei"],)),
            ("""
                INSERT INTO historial_asignaciones
                (asignacion_id, empleado_id, linea_id, imei, fecha_inicio, fecha_fin, tipo_movimiento, motivo)
                VALUES (%s, %s, %s, %s, NOW(), NOW(), 'Baja', %s)
            """, (id, asignacion["empleado_id"], asignacion["linea_id"], asignacion["imei"], motivo))
        ])

        return jsonify({"ok": True, "msg": "Asignación cerrada correctamente"})

    except Exception as e:
        return api_error(e)


@asignaciones_bp.route("/asignacion/<id>/reasignar", methods=["GET", "POST"])
def reasignar_asignacion(id):
    if request.method == "GET":
        asignacion = fetch_one("""
            SELECT a.id, a.empleado_id, a.linea_id, a.imei,
                   CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
                   IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS linea,
                   eq.modelo
            FROM asignaciones a
            JOIN empleados e ON e.id = a.empleado_id
            JOIN lineas l ON l.id = a.linea_id
            JOIN equipos eq ON eq.imei = a.imei
            WHERE a.id = %s AND a.estatus = 'Vigente'
        """, (id,))

        if not asignacion:
            return "Asignación no encontrada", 404

        empleados = fetch_all("SELECT id, nombre FROM empleados WHERE estatus = 'Activo' ORDER BY nombre")
        return render_template("reasignar_asignacion.html", asignacion=asignacion, empleados=empleados)

    try:
        data = request.get_json(force=True)
        nuevo_empleado_id = (data.get("nuevo_empleado_id") or "").strip()
        nuevo_imei = (data.get("nuevo_imei") or "").strip()
        motivo = (data.get("motivo") or "").strip() or "Reasignación"

        asignacion = fetch_one("""
            SELECT id, empleado_id, linea_id, imei FROM asignaciones
            WHERE id = %s AND estatus = 'Vigente'
        """, (id,))

        if not asignacion:
            return jsonify({"ok": False, "msg": "Asignación no encontrada"}), 404

        if nuevo_empleado_id and not fetch_one("SELECT 1 FROM empleados WHERE id = %s AND estatus = 'Activo'", (nuevo_empleado_id,)):
            return jsonify({"ok": False, "msg": "El nuevo empleado no existe"}), 400

        if nuevo_imei and nuevo_imei != asignacion["imei"]:
            equipo = fetch_one("SELECT imei, estatus FROM equipos WHERE imei = %s", (nuevo_imei,))
            if not equipo:
                return jsonify({"ok": False, "msg": "El nuevo equipo no existe"}), 400
            if equipo["estatus"] != "Disponible":
                return jsonify({"ok": False, "msg": f"El equipo no está disponible (estado: {equipo['estatus']})"}), 400

        nuevo_emp = nuevo_empleado_id or asignacion["empleado_id"]
        nuevo_eq = nuevo_imei or asignacion["imei"]
        device_changed = nuevo_eq != asignacion["imei"]

        statements = [
            ("""
                UPDATE asignaciones SET empleado_id = %s, imei = %s WHERE id = %s
            """, (nuevo_emp, nuevo_eq, id)),
        ]
        if device_changed:
            statements += [
                ("""UPDATE equipos SET estatus = 'Disponible' WHERE imei = %s""", (asignacion["imei"],)),
                ("""UPDATE equipos SET estatus = 'Asignado' WHERE imei = %s""", (nuevo_eq,)),
            ]
        statements.append(("""
                INSERT INTO historial_asignaciones
                (asignacion_id, empleado_id, linea_id, imei, fecha_inicio, tipo_movimiento, motivo)
                VALUES (%s, %s, %s, %s, NOW(), 'Reasignacion', %s)
            """, (id, nuevo_emp, asignacion["linea_id"], nuevo_eq, motivo)))

        execute_transaction(statements)

        return jsonify({"ok": True, "msg": "Asignación reasignada correctamente"})

    except Exception as e:
        return api_error(e)



@asignaciones_bp.route("/api/equipos_disponibles", methods=["GET"])
def api_equipos_disponibles():
    equipos = fetch_all("""
        SELECT imei AS id, COALESCE(modelo, imei) AS label
        FROM equipos
        WHERE estatus = 'Disponible'
        ORDER BY modelo, imei
    """)
    return jsonify(equipos)


@asignaciones_bp.route("/asignacion/<id>/historial", methods=["GET"])
def historial_asignacion(id):
    asignacion = fetch_one("""
        SELECT a.id, a.empleado_id, a.linea_id, a.imei,
               CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
               IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS linea,
               eq.modelo
        FROM asignaciones a
        JOIN empleados e ON e.id = a.empleado_id
        JOIN lineas l ON l.id = a.linea_id
        JOIN equipos eq ON eq.imei = a.imei
        WHERE a.id = %s
    """, (id,))

    if not asignacion:
        return "Asignación no encontrada", 404

    historial = fetch_all("""
        SELECT
            ha.fecha_inicio,
            ha.fecha_fin,
            ha.tipo_movimiento,
            ha.motivo,
            CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
            IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS linea,
            ha.imei,
            eq.modelo
        FROM historial_asignaciones ha
        JOIN empleados e ON e.id = ha.empleado_id
        JOIN lineas l ON l.id = ha.linea_id
        JOIN equipos eq ON eq.imei = ha.imei
        WHERE ha.asignacion_id = %s
        ORDER BY ha.fecha_inicio DESC
    """, (id,))

    return render_template("historial_asignacion.html", asignacion=asignacion, historial=historial)


@asignaciones_bp.route("/linea/<id>/historial", methods=["GET"])
def historial_linea(id):
    linea = fetch_one("""
        SELECT l.id, l.lada, l.numero, l.plan, l.estatus,
               IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS telefono
        FROM lineas l
        WHERE l.id = %s
    """, (id,))

    if not linea:
        return "Línea no encontrada", 404

    historial = fetch_all("""
        SELECT
            ha.fecha_inicio,
            ha.fecha_fin,
            ha.tipo_movimiento,
            ha.motivo,
            CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
            ha.imei,
            eq.modelo
        FROM historial_asignaciones ha
        JOIN empleados e ON e.id = ha.empleado_id
        JOIN equipos eq ON eq.imei = ha.imei
        WHERE ha.linea_id = %s
        ORDER BY ha.fecha_inicio DESC
    """, (id,))

    return render_template("historial_linea.html", linea=linea, historial=historial)


@asignaciones_bp.route("/equipo/<imei>/historial", methods=["GET"])
def historial_equipo(imei):
    equipo = fetch_one("""
        SELECT imei, marca, modelo, serial, estatus
        FROM equipos
        WHERE imei = %s
    """, (imei,))

    if not equipo:
        return "Equipo no encontrado", 404

    historial = fetch_all("""
        SELECT
            ha.fecha_inicio,
            ha.fecha_fin,
            ha.tipo_movimiento,
            ha.motivo,
            CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
            IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS linea
        FROM historial_asignaciones ha
        JOIN empleados e ON e.id = ha.empleado_id
        JOIN lineas l ON l.id = ha.linea_id
        WHERE ha.imei = %s
        ORDER BY ha.fecha_inicio DESC
    """, (imei,))

    return render_template("historial_equipo.html", equipo=equipo, historial=historial)
