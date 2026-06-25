import uuid
from flask import Blueprint, request, render_template, jsonify
from utils import fetch_all, fetch_one, execute_query, execute_transaction, api_error, leer_csv, campo

lineas_bp = Blueprint('lineas', __name__)


@lineas_bp.route("/api/lineas", methods=["GET"])
def api_lineas():
    lineas = fetch_all("""
        SELECT l.id, IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS label
        FROM lineas l
        WHERE l.estatus = 'Disponible'
        ORDER BY l.lada, l.numero
    """)
    return jsonify(lineas)


@lineas_bp.route("/lineas", methods=["GET", "POST"])
def lista_lineas():
    if request.method == "GET":
        lineas = fetch_all("""
            SELECT
                l.id,
                l.lada,
                l.numero,
                IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS telefono,
                l.plan,
                l.iccid,
                l.cuenta_padre_id,
                l.estatus,
                cp.operador,
                e.nombre AS empleado_nombre,
                a.nombre AS area_nombre,
                eq.imei AS equipo_imei
            FROM lineas l
            LEFT JOIN cuentas_padre cp ON cp.id = l.cuenta_padre_id
            LEFT JOIN asignaciones a_vigente ON a_vigente.linea_id = l.id
                AND a_vigente.estatus = 'Vigente' AND a_vigente.fecha_fin IS NULL
            LEFT JOIN empleados e ON e.id = a_vigente.empleado_id
            LEFT JOIN areas a ON a.id = e.area_id
            LEFT JOIN equipos eq ON eq.imei = a_vigente.imei
            ORDER BY l.lada, l.numero
            LIMIT 100
        """)
        return render_template("lista_lineas.html", lineas=lineas)

    try:
        data = request.get_json(force=True)
        linea_id = data.get("id")

        deps = fetch_one("""
            SELECT COUNT(a.id) AS asignaciones_vigentes
            FROM asignaciones a
            WHERE a.linea_id = %s AND a.estatus = 'Vigente' AND a.fecha_fin IS NULL
        """, (linea_id,))

        if deps and deps["asignaciones_vigentes"] > 0:
            return jsonify({
                "ok": False,
                "msg": f"Línea tiene {deps['asignaciones_vigentes']} asignación(es) vigente(s)"
            }), 400

        execute_query("UPDATE lineas SET estatus = 'Baja' WHERE id = %s", (linea_id,))
        return jsonify({"ok": True, "msg": "Línea marcada como baja correctamente"})

    except Exception as e:
        return api_error(e)


def _parse_telefono(raw):
    if not raw:
        return None, None, "El teléfono es obligatorio"
    raw = str(raw).strip()
    num_str = "".join(c for c in raw if c.isdigit())
    if not num_str:
        return None, None, "El teléfono debe contener números"
    if len(num_str) != 10:
        return None, None, "El teléfono debe tener exactamente 10 dígitos"
    try:
        return 0, int(num_str), None
    except ValueError:
        return None, None, "El teléfono tiene un formato inválido"


@lineas_bp.route("/linea/crear", methods=["POST"])
def crear_lineas():
    try:
        data = request.get_json(force=True)

        id_linea = (data.get("id") or "").strip()
        telefono = (data.get("telefono") or "").strip()
        plan = (data.get("plan") or "").strip()
        iccid = (data.get("iccid") or "").strip() or None
        cuenta_padre_id = (data.get("cuenta_padre_id") or "").strip()

        if not id_linea:
            return jsonify({"ok": False, "msg": "El id de la línea es obligatorio"}), 400
        if not plan or not cuenta_padre_id:
            return jsonify({"ok": False, "msg": "Plan y cuenta padre son obligatorios"}), 400

        lada, numero, err = _parse_telefono(telefono)
        if err:
            return jsonify({"ok": False, "msg": err}), 400

        if not fetch_one("SELECT 1 FROM cuentas_padre WHERE id = %s", (cuenta_padre_id,)):
            return jsonify({"ok": False, "msg": "La cuenta padre no existe"}), 400

        execute_query("""
            INSERT INTO lineas (id, cuenta_padre_id, lada, numero, plan, iccid, estatus)
            VALUES (%s, %s, %s, %s, %s, %s, 'Disponible')
        """, (id_linea, cuenta_padre_id, lada, numero, plan, iccid))

        return jsonify({"ok": True, "msg": "Línea creada correctamente", "redirect": "/lineas"}), 201

    except Exception as e:
        return api_error(e)


@lineas_bp.route("/lineas/importar", methods=["POST"])
def importar_lineas():
    """Importación masiva de líneas desde CSV.

    Columnas esperadas: numero, cuenta_padre, iccid, plan
    - 'numero': 10 dígitos.
    - 'cuenta_padre': código de la cuenta padre (debe existir).
    - 'iccid': opcional.
    - 'plan': obligatorio.
    El id se genera automáticamente (UUID). Validación todo-o-nada:
    si hay algún error no se inserta nada.
    """
    try:
        file = request.files.get("archivo")
        if not file or not file.filename:
            return jsonify({"ok": False, "msg": "No se recibió ningún archivo"}), 400
        if not file.filename.lower().endswith(".csv"):
            return jsonify({"ok": False, "msg": "El archivo debe ser .csv"}), 400

        filas, err = leer_csv(file)
        if err:
            return jsonify({"ok": False, "msg": err}), 400
        if not filas:
            return jsonify({"ok": False, "msg": "El archivo no tiene filas de datos"}), 400

        # Catálogos en memoria para validar sin N consultas
        cuentas = {(r["codigo"] or "").strip(): r["id"]
                   for r in fetch_all("SELECT id, codigo FROM cuentas_padre")}
        numeros_db = {r["numero"] for r in fetch_all("SELECT numero FROM lineas")}
        iccids_db = {r["iccid"] for r in fetch_all("SELECT iccid FROM lineas WHERE iccid IS NOT NULL")}

        statements = []
        errores = []
        numeros_vistos = set()
        iccids_vistos = set()

        for i, row in enumerate(filas, start=2):  # fila 1 = encabezado
            numero_raw = campo(row, "numero", "linea", "telefono")
            cuenta_cod = campo(row, "cuenta_padre", "cuenta padre", "codigo", "cuenta")
            iccid = campo(row, "iccid", "ssid", "sim") or None
            plan = campo(row, "plan")

            lada, numero, perr = _parse_telefono(numero_raw)
            if perr:
                errores.append(f"Fila {i}: {perr}")
                continue
            if not cuenta_cod:
                errores.append(f"Fila {i}: falta la cuenta padre")
                continue
            if cuenta_cod not in cuentas:
                errores.append(f"Fila {i}: la cuenta padre '{cuenta_cod}' no existe")
                continue
            if not plan:
                errores.append(f"Fila {i}: el plan es obligatorio")
                continue
            if iccid and len(iccid) > 20:
                errores.append(f"Fila {i}: el ICCID es demasiado largo (máx 20 caracteres)")
                continue
            if numero in numeros_db or numero in numeros_vistos:
                errores.append(f"Fila {i}: el número {numero} ya existe o está duplicado en el archivo")
                continue
            if iccid and (iccid in iccids_db or iccid in iccids_vistos):
                errores.append(f"Fila {i}: el ICCID {iccid} ya existe o está duplicado en el archivo")
                continue

            numeros_vistos.add(numero)
            if iccid:
                iccids_vistos.add(iccid)

            statements.append((
                """INSERT INTO lineas (id, cuenta_padre_id, lada, numero, plan, iccid, estatus)
                   VALUES (%s, %s, %s, %s, %s, %s, 'Disponible')""",
                (str(uuid.uuid4()), cuentas[cuenta_cod], lada, numero, plan, iccid)
            ))

        if errores:
            return jsonify({
                "ok": False,
                "msg": f"No se importó nada. Se encontraron {len(errores)} error(es); corrige el archivo.",
                "errores": errores[:50]
            }), 400

        execute_transaction(statements)
        return jsonify({"ok": True, "msg": f"Se importaron {len(statements)} línea(s) correctamente."})

    except Exception as e:
        return api_error(e)


@lineas_bp.route("/linea/editar/<id>", methods=["POST"])
def actualizar_lineas(id):
    try:
        data = request.get_json(force=True)

        nuevo_telefono = (data.get("nuevo_telefono") or "").strip()
        nuevo_plan = (data.get("nuevo_plan") or "").strip()
        nuevo_iccid = (data.get("nuevo_iccid") or "").strip() or None
        nuevo_cuenta = (data.get("nuevo_cuenta_padre_id") or "").strip()

        actual = fetch_one(
            "SELECT id, lada, numero, plan, iccid, cuenta_padre_id, estatus FROM lineas WHERE id = %s", (id,)
        )
        if not actual:
            return jsonify({"ok": False, "msg": "Línea no encontrada"}), 404

        # Parsear teléfono si vino, sino mantener el actual
        if nuevo_telefono:
            nuevo_lada, nuevo_numero, err = _parse_telefono(nuevo_telefono)
            if err:
                return jsonify({"ok": False, "msg": err}), 400
        else:
            nuevo_lada = actual["lada"]
            nuevo_numero = actual["numero"]

        nuevo_id = actual["id"]
        if not nuevo_plan:
            nuevo_plan = actual["plan"]
        if nuevo_iccid is None:
            nuevo_iccid = actual["iccid"]
        if not nuevo_cuenta:
            nuevo_cuenta = actual["cuenta_padre_id"]

        if not fetch_one("SELECT 1 FROM cuentas_padre WHERE id = %s", (nuevo_cuenta,)):
            return jsonify({"ok": False, "msg": "La cuenta padre no existe"}), 400

        execute_query("""
            UPDATE lineas
            SET id = %s, lada = %s, numero = %s, plan = %s, iccid = %s, cuenta_padre_id = %s
            WHERE id = %s
        """, (nuevo_id, nuevo_lada, nuevo_numero, nuevo_plan, nuevo_iccid, nuevo_cuenta, id))

        return jsonify({"ok": True, "msg": "Línea actualizada correctamente"})

    except Exception as e:
        return api_error(e)
