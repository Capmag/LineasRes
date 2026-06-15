from flask import Blueprint, request, render_template, jsonify
from utils import fetch_all, fetch_one, execute_query, api_error

areas_bp = Blueprint('areas', __name__)


@areas_bp.route("/api/areas", methods=["GET"])
def api_areas():
    areas = fetch_all("""
        SELECT a.id, CONCAT(a.nombre, ' — ', cc.nombre) AS label
        FROM areas a
        JOIN centros_costo cc ON cc.id = a.centro_costo_id
        ORDER BY cc.nombre, a.nombre
    """)
    return jsonify(areas)


@areas_bp.route("/areas", methods=["GET", "POST"])
def lista_area():
    if request.method == "GET":
        areas = fetch_all("""
            SELECT
                a.id, a.nombre,
                a.centro_costo_id,
                cc.nombre AS centro_costos,
                COUNT(DISTINCT e.id) AS empleados_count
            FROM areas a
            JOIN centros_costo cc ON cc.id = a.centro_costo_id
            LEFT JOIN empleados e ON e.area_id = a.id
            GROUP BY a.id, a.nombre, a.centro_costo_id, cc.nombre
            ORDER BY a.nombre
            LIMIT 100
        """)
        return render_template("lista_areas.html", areas=areas)

    try:
        data = request.get_json(force=True)
        area_id = data.get("id")

        deps = fetch_one("""
            SELECT COUNT(DISTINCT e.id) AS emp_count
            FROM areas a
            LEFT JOIN empleados e ON e.area_id = a.id
            WHERE a.id = %s
        """, (area_id,))

        if deps and deps["emp_count"] > 0:
            msg = f"No se puede eliminar, tiene {deps['emp_count']} empleado(s) asociado(s)"
            return jsonify({"ok": False, "msg": msg}), 400

        execute_query("DELETE FROM areas WHERE id = %s", (area_id,))
        return jsonify({"ok": True, "msg": "Área eliminada correctamente"})

    except Exception as e:
        return api_error(e)


@areas_bp.route("/area/crear", methods=["GET", "POST"])
def crear_area():
    if request.method == "GET":
        centros = fetch_all("SELECT id, nombre FROM centros_costo ORDER BY nombre")
        return render_template("crear_area.html", centros_costos=centros)

    try:
        data = request.get_json(force=True)

        id_area = (data.get("id") or data.get("idArea") or "").strip()
        nombre_area = (data.get("nombre") or data.get("nombreArea") or "").strip()
        id_cc = (data.get("centro_costo_id") or data.get("idCentroCosto") or "").strip()

        if not id_area:
            return jsonify({"ok": False, "msg": "El id del área es obligatorio"}), 400
        if not nombre_area:
            return jsonify({"ok": False, "msg": "El nombre del área es obligatorio"}), 400
        if not id_cc:
            return jsonify({"ok": False, "msg": "El id del centro de costos es obligatorio"}), 400

        if not fetch_one("SELECT 1 FROM centros_costo WHERE id = %s", (id_cc,)):
            return jsonify({"ok": False, "msg": "El centro de costo no existe"}), 400

        execute_query(
            "INSERT INTO areas (id, nombre, centro_costo_id) VALUES (%s, %s, %s)",
            (id_area, nombre_area, id_cc)
        )
        return jsonify({"ok": True, "msg": "Área creada correctamente", "redirect": "/areas"}), 201

    except Exception as e:
        return api_error(e)


@areas_bp.route("/area/editar/<id>", methods=["GET", "POST"])
def actualizar_area(id):
    if request.method == "GET":
        area = fetch_one("""
            SELECT id, nombre, centro_costo_id AS centro_costos
            FROM areas WHERE id = %s
        """, (id,))
        if not area:
            return "Área no encontrada", 404
        return render_template("actualizar_area.html", area=area)

    try:
        data = request.get_json(force=True)

        nuevo_id = (data.get("nuevo_id") or "").strip()
        nuevo_nombre = (data.get("nuevo_nombre") or "").strip()
        nuevo_cc = (data.get("nuevo_cc") or "").strip()

        actual = fetch_one(
            "SELECT id, nombre, centro_costo_id FROM areas WHERE id = %s", (id,)
        )
        if not actual:
            return jsonify({"ok": False, "msg": "Área no encontrada"}), 404

        if not nuevo_id:
            nuevo_id = actual["id"]
        if not nuevo_nombre:
            nuevo_nombre = actual["nombre"]
        if not nuevo_cc:
            nuevo_cc = actual["centro_costo_id"]

        if not fetch_one("SELECT 1 FROM centros_costo WHERE id = %s", (nuevo_cc,)):
            return jsonify({"ok": False, "msg": "El centro de costo no existe"}), 400

        execute_query(
            "UPDATE areas SET id = %s, nombre = %s, centro_costo_id = %s WHERE id = %s",
            (nuevo_id, nuevo_nombre, nuevo_cc, id)
        )
        return jsonify({"ok": True, "msg": "Área actualizada correctamente"})

    except Exception as e:
        return api_error(e)


