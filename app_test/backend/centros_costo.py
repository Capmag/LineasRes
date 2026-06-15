from flask import Blueprint, request, render_template, jsonify
import uuid
from utils import fetch_all, fetch_one, execute_query, api_error

cc_bp = Blueprint('cc', __name__)


@cc_bp.route("/api/centros_costo", methods=["GET"])
def api_centros_costo():
    ccs = fetch_all("""
        SELECT
            cc.id,
            CASE
                WHEN d.id IS NOT NULL
                THEN CONCAT(cc.nombre, ' — ', d.nombre, COALESCE(CONCAT(' ', d.apellido), ''))
                ELSE cc.nombre
            END AS label
        FROM centros_costo cc
        LEFT JOIN directores d ON d.id = cc.director_id
        ORDER BY cc.nombre
    """)
    return jsonify(ccs)


@cc_bp.route("/centroscostos", methods=["GET", "POST"])
def lista_cc():
    if request.method == "GET":
        centros_costos = fetch_all("""
            SELECT
                cc.id,
                cc.nombre,
                cc.director_id,
                CONCAT(d.nombre, ' ', COALESCE(d.apellido, '')) AS director_nombre,
                COUNT(DISTINCT a.id) AS areas_count
            FROM centros_costo cc
            LEFT JOIN directores d ON d.id = cc.director_id
            LEFT JOIN areas a ON a.centro_costo_id = cc.id
            GROUP BY cc.id, cc.nombre, cc.director_id, d.nombre, d.apellido
            ORDER BY cc.nombre
            LIMIT 100
        """)
        return render_template("lista_cc.html", centros_costos=centros_costos)

    try:
        data = request.get_json(force=True)
        cc_id = data.get("id")

        deps = fetch_one("""
            SELECT COUNT(DISTINCT a.id) AS areas_count
            FROM centros_costo cc
            LEFT JOIN areas a ON a.centro_costo_id = cc.id
            WHERE cc.id = %s
        """, (cc_id,))

        if deps and deps["areas_count"] > 0:
            msg = f"No se puede eliminar, tiene {deps['areas_count']} área(s) asociada(s)"
            return jsonify({"ok": False, "msg": msg}), 400

        execute_query("DELETE FROM centros_costo WHERE id = %s", (cc_id,))
        return jsonify({"ok": True, "msg": "Centro de costos eliminado correctamente"})

    except Exception as e:
        return api_error(e)


@cc_bp.route("/cc/crear", methods=["POST"])
def crear_cc():
    try:
        data = request.get_json(force=True)

        cc_id = (data.get("id") or "").strip() or str(uuid.uuid4())
        nombre = (data.get("nombre") or "").strip()
        director_id = (data.get("director_id") or "").strip() or None

        if not nombre:
            return jsonify({"ok": False, "msg": "El nombre del centro de costos es obligatorio"}), 400

        if director_id:
            if not fetch_one("SELECT 1 FROM directores WHERE id = %s", (director_id,)):
                return jsonify({"ok": False, "msg": "El director no existe"}), 400

        execute_query("""
            INSERT INTO centros_costo (id, nombre, director_id)
            VALUES (%s, %s, %s)
        """, (cc_id, nombre, director_id))

        return jsonify({
            "ok": True,
            "msg": "Centro de costos creado correctamente"
        }), 201

    except Exception as e:
        return api_error(e)


@cc_bp.route("/cc/editar/<id>", methods=["POST"])
def actualizar_cc(id):
    try:
        data = request.get_json(force=True)

        nuevo_id = (data.get("id") or "").strip() or None
        nuevo_nombre = (data.get("nombre") or "").strip()

        actual = fetch_one("""
            SELECT id, nombre, director_id
            FROM centros_costo WHERE id = %s
        """, (id,))

        if not actual:
            return jsonify({"ok": False, "msg": "Centro de costos no encontrado"}), 404

        if not nuevo_id:
            nuevo_id = actual["id"]
        if not nuevo_nombre:
            nuevo_nombre = actual["nombre"]
        # Si director_id no vino en el payload, conservar el valor existente.
        # Si vino explícitamente (aunque sea null), aplicarlo (permite quitar el director).
        if "director_id" in data:
            nuevo_dir_id = (data.get("director_id") or "").strip() or None
        else:
            nuevo_dir_id = actual["director_id"]

        if nuevo_dir_id:
            if not fetch_one("SELECT 1 FROM directores WHERE id = %s", (nuevo_dir_id,)):
                return jsonify({"ok": False, "msg": "El director no existe"}), 400

        execute_query("""
            UPDATE centros_costo
            SET id = %s, nombre = %s, director_id = %s
            WHERE id = %s
        """, (nuevo_id, nuevo_nombre, nuevo_dir_id, id))

        return jsonify({"ok": True, "msg": "Centro de costos actualizado correctamente"})

    except Exception as e:
        return api_error(e)
