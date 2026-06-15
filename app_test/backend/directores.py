from flask import Blueprint, request, render_template, jsonify, redirect, url_for
from utils import fetch_all, fetch_one, execute_query, api_error, get_payload, clean, clean_or_none

directores_bp = Blueprint('directores', __name__)


@directores_bp.route("/api/directores", methods=["GET"])
def api_directores():
    directores = fetch_all("""
        SELECT id, CONCAT(nombre, ' ', COALESCE(apellido, '')) AS label
        FROM directores
        ORDER BY nombre, apellido
    """)
    return jsonify(directores)


@directores_bp.route("/directores", methods=["GET", "POST"])
def lista_directores():
    if request.method == "GET":
        directores = fetch_all("""
            SELECT id, nombre, apellido,
                   CONCAT(nombre, ' ', COALESCE(apellido, '')) AS nombre_completo
            FROM directores
            ORDER BY nombre, apellido
            LIMIT 100
        """)
        return render_template("lista_directores.html", directores=directores)

    try:
        data = request.get_json(force=True)
        director_id = data.get("id")

        count_cc = fetch_one(
            "SELECT COUNT(*) AS count FROM centros_costo WHERE director_id = %s",
            (director_id,)
        )
        if count_cc and count_cc["count"] > 0:
            return jsonify({
                "ok": False,
                "msg": f"No se puede eliminar, tiene {count_cc['count']} centros de costo asignados"
            }), 400

        execute_query("DELETE FROM directores WHERE id = %s", (director_id,))
        return jsonify({"ok": True, "msg": "Director eliminado"})

    except Exception as e:
        return api_error(e)


@directores_bp.route("/director/crear", methods=["GET", "POST"])
def crear_directores():
    if request.method == "GET":
        return render_template("crear_director.html")

    try:
        payload = get_payload()

        director_id = clean(payload.get("id"))
        nombre = clean(payload.get("nombre"))
        apellido = clean_or_none(payload.get("apellido"))

        if not director_id:
            return jsonify({"ok": False, "msg": "El id del director es obligatorio"}), 400
        if not nombre:
            return jsonify({"ok": False, "msg": "El nombre del director es obligatorio"}), 400

        execute_query(
            "INSERT INTO directores (id, nombre, apellido) VALUES (%s, %s, %s)",
            (director_id, nombre, apellido)
        )
        return jsonify({
            "ok": True,
            "msg": "Director creado correctamente",
            "redirect": url_for("directores.lista_directores")
        }), 201

    except Exception as e:
        return api_error(e)


@directores_bp.route("/director/editar/<id>", methods=["GET", "POST"])
def actualizar_directores(id):
    if request.method == "GET":
        director = fetch_one(
            "SELECT id, nombre, apellido FROM directores WHERE id = %s", (id,)
        )
        if not director:
            return "Director no encontrado", 404
        return render_template("actualizar_director.html", director=director)

    try:
        payload = get_payload()
        nombre = clean(payload.get("nombre"))
        apellido = clean_or_none(payload.get("apellido"))

        if not nombre:
            return jsonify({"ok": False, "msg": "El nombre del director es obligatorio"}), 400

        execute_query(
            "UPDATE directores SET nombre = %s, apellido = %s WHERE id = %s",
            (nombre, apellido, id)
        )
        return jsonify({"ok": True, "msg": "Director actualizado correctamente"})

    except Exception as e:
        return api_error(e)
