from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import check_password_hash
from utils import fetch_one

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            if request.is_json or request.headers.get('X-CSRFToken'):
                return jsonify({"ok": False, "msg": "Sesión expirada. Recarga la página."}), 401
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        password = request.form.get('password') or ''

        user = fetch_one(
            "SELECT id, username, password_hash, nombre, activo FROM usuarios WHERE username = 'admin'"
        )

        if not user or not user['activo'] or not check_password_hash(user['password_hash'], password):
            error = 'Contraseña incorrecta'
        else:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['nombre'] = user['nombre'] or 'Admin'
            return redirect(url_for('index'))

    return render_template('login.html', error=error)


@auth_bp.route('/login/consultas')
def login_consultas():
    user = fetch_one(
        "SELECT id, username, nombre, activo FROM usuarios WHERE username = 'consultas'"
    )
    if not user or not user['activo']:
        return redirect(url_for('auth.login'))
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['nombre'] = user['nombre'] or 'Consultas'
    return redirect(url_for('index'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
