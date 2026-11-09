
import secrets
import hmac
from pathlib import Path
from functools import wraps

from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_connection, initialize_database


# =====================================
# APPLICATION CONFIGURATION
# =====================================

BASE_DIR = Path(__file__).resolve().parent
SECRET_FILE = BASE_DIR / ".secret_key"

if SECRET_FILE.exists():
    SECRET_KEY = SECRET_FILE.read_text().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    SECRET_FILE.write_text(SECRET_KEY)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


# =====================================
# RESPONSE HELPER
# =====================================

def make_response(message, status=200, **extra):
    return jsonify({"message": message, **extra}), status


# =====================================
# CSRF PROTECTION
# =====================================

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    return session["csrf_token"]


def verify_csrf():
    supplied = request.headers.get("X-CSRF-Token", "")
    saved = session.get("csrf_token", "")

    if not supplied or not saved:
        return False

    return hmac.compare_digest(supplied, saved)


@app.get("/api/csrf-token")
def csrf_token_route():
    return jsonify({"csrf_token": get_csrf_token()})


# =====================================
# LOGIN AND ROLE PROTECTION
# =====================================

def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:
            return make_response("Please log in first.", 401)

        return view_function(*args, **kwargs)

    return wrapped_view


def role_required(*allowed_roles):
    def decorator(view_function):

        @wraps(view_function)
        def wrapped_view(*args, **kwargs):

            if "user_id" not in session:
                return make_response("Please log in first.", 401)

            if session.get("role") not in allowed_roles:
                return make_response("Access denied.", 403)

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


# =====================================
# HOMEPAGE
# =====================================

@app.get("/")
def home():
    return render_template("index.html")


@app.get("/register")
def register_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.get("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.get("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role")
    if role == "seeker":
        return redirect(url_for("seeker_page"))
    if role == "owner":
        return redirect(url_for("owner_page"))
    if role == "admin":
        return redirect(url_for("admin_page"))

    session.clear()
    return redirect(url_for("login_page"))


@app.get("/seeker")
@role_required("seeker")
def seeker_page():
    return render_template("seeker_dashboard.html")


@app.get("/owner")
@role_required("owner")
def owner_page():
    return render_template("owner_dashboard.html")


@app.get("/admin")
@role_required("admin")
def admin_page():
    return render_template("admin_dashboard.html")


# =====================================
# DATABASE TEST
# =====================================

@app.get("/api/test-db")
def test_database():

    connection = get_connection()

    try:
        users = connection.execute(
            "SELECT COUNT(*) AS total FROM users"
        ).fetchone()["total"]

        properties = connection.execute(
            "SELECT COUNT(*) AS total FROM properties"
        ).fetchone()["total"]

        return jsonify({
            "database": "connected",
            "users": users,
            "properties": properties
        })

    finally:
        connection.close()


# =====================================
# USER REGISTRATION
# =====================================

@app.post("/api/register")
def register():

    if not verify_csrf():
        return make_response("Invalid security token.", 403)

    data = request.get_json(silent=True) or {}

    full_name = str(data.get("full_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    role = data.get("role", "")

    if not full_name or not email or not password or not role:
        return make_response("Complete all required fields.", 400)

    if len(full_name) > 100 or len(email) > 150:
        return make_response("Name or email is too long.", 400)

    if "@" not in email or "." not in email.split("@")[-1]:
        return make_response("Enter a valid email address.", 400)

    if not isinstance(password, str) or len(password) < 8:
        return make_response("Password must have at least 8 characters.", 400)

    if len(password) > 128:
        return make_response("Password is too long.", 400)

    if role not in ("seeker", "owner"):
        return make_response("Invalid account role.", 400)

    password_hash = generate_password_hash(password)

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO users
            (full_name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, email, password_hash, role)
        )

        connection.commit()

        return make_response(
            "Account created successfully.",
            201,
            user_id=cursor.lastrowid
        )

    except Exception as error:

        if "UNIQUE constraint failed" in str(error):
            return make_response("Email already registered.", 409)

        app.logger.exception("Registration error")
        return make_response("Registration failed.", 500)

    finally:
        connection.close()


# =====================================
# USER LOGIN
# =====================================

@app.post("/api/login")
def login():

    if not verify_csrf():
        return make_response("Invalid security token.", 403)

    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not email or not isinstance(password, str) or not password:
        return make_response("Enter email and password.", 400)

    connection = get_connection()

    try:
        user = connection.execute(
            """
            SELECT id, full_name, email, password_hash, role
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if user is None or not check_password_hash(
            user["password_hash"], password
        ):
            return make_response("Invalid email or password.", 401)

        session.clear()

        session["user_id"] = user["id"]
        session["full_name"] = user["full_name"]
        session["role"] = user["role"]
        session["csrf_token"] = secrets.token_hex(32)

        return jsonify({
            "message": "Login successful.",
            "user": {
                "id": user["id"],
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"]
            },
            "csrf_token": session["csrf_token"]
        })

    finally:
        connection.close()


# =====================================
# CURRENT USER
# =====================================

@app.get("/api/me")
@login_required
def current_user():

    return jsonify({
        "user_id": session["user_id"],
        "full_name": session["full_name"],
        "role": session["role"]
    })


# =====================================
# LOGOUT
# =====================================

@app.post("/api/logout")
@login_required
def logout():

    if not verify_csrf():
        return make_response("Invalid security token.", 403)

    session.clear()

    return make_response("Logged out successfully.")


# =====================================
# VIEW PROPERTIES
# =====================================

@app.get("/api/properties")
@login_required
def view_properties():

    connection = get_connection()

    try:
        if session.get("role") == "owner":
            properties = connection.execute(
                """
                SELECT properties.id, properties.title,
                       properties.description, properties.location,
                       properties.price, properties.owner_id,
                       users.full_name AS owner_name
                FROM properties
                JOIN users ON properties.owner_id = users.id
                WHERE properties.owner_id = ?
                ORDER BY properties.created_at DESC
                """,
                (session["user_id"],)
            ).fetchall()
        else:
            properties = connection.execute(
                """
                SELECT properties.id, properties.title,
                       properties.description, properties.location,
                       properties.price, properties.owner_id,
                       users.full_name AS owner_name
                FROM properties
                JOIN users ON properties.owner_id = users.id
                ORDER BY properties.created_at DESC
                """
            ).fetchall()

        return jsonify([dict(p) for p in properties])

    finally:
        connection.close()


# =====================================
# ADD PROPERTY - OWNER ONLY
# =====================================

@app.post("/api/properties")
@role_required("owner")
def add_property():

    if not verify_csrf():
        return make_response("Invalid security token.", 403)

    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    location = str(data.get("location", "")).strip()
    price = data.get("price")

    if not title or not description or not location or price is None:
        return make_response("Complete all property fields.", 400)

    if len(title) > 150 or len(description) > 2000 or len(location) > 150:
        return make_response("One or more fields are too long.", 400)

    try:
        price = float(price)

        if not 0 <= price <= 1000000000000:
            raise ValueError

    except (ValueError, TypeError):
        return make_response("Enter a valid price.", 400)

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO properties
            (title, description, location, price, owner_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, description, location, price, session["user_id"])
        )

        connection.commit()

        return make_response(
            "Property added successfully.",
            201,
            property_id=cursor.lastrowid
        )

    finally:
        connection.close()


# =====================================
# EDIT PROPERTY - OWNER ONLY
# =====================================

@app.put("/api/properties/<int:property_id>")
@role_required("owner")
def edit_property(property_id):

    if not verify_csrf():
        return make_response("Invalid security token.", 403)

    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    location = str(data.get("location", "")).strip()
    price = data.get("price")

    if not title or not description or not location or price is None:
        return make_response("Complete all property fields.", 400)

    if len(title) > 150 or len(description) > 2000 or len(location) > 150:
        return make_response("One or more fields are too long.", 400)

    try:
        price = float(price)

        if not 0 <= price <= 1000000000000:
            raise ValueError

    except (ValueError, TypeError):
        return make_response("Enter a valid price.", 400)

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE properties
            SET title = ?, description = ?, location = ?, price = ?
            WHERE id = ? AND owner_id = ?
            """,
            (
                title, description, location, price,
                property_id, session["user_id"]
            )
        )

        connection.commit()

        if cursor.rowcount == 0:
            return make_response("Property not found or access denied.", 404)

        return make_response("Property updated successfully.")

    finally:
        connection.close()


# =====================================
# DELETE PROPERTY - OWNER ONLY
# =====================================

@app.delete("/api/properties/<int:property_id>")
@role_required("owner")
def delete_property(property_id):

    if not verify_csrf():
        return make_response("Invalid security token.", 403)

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            DELETE FROM properties
            WHERE id = ? AND owner_id = ?
            """,
            (property_id, session["user_id"])
        )

        connection.commit()

        if cursor.rowcount == 0:
            return make_response("Property not found or access denied.", 404)

        return make_response("Property deleted successfully.")

    finally:
        connection.close()


# =====================================
# ADMIN - VIEW USERS
# =====================================

@app.get("/api/admin/users")
@role_required("admin")
def admin_view_users():

    connection = get_connection()

    try:
        users = connection.execute(
            """
            SELECT id, full_name, email, role, created_at
            FROM users
            ORDER BY created_at DESC
            """
        ).fetchall()

        return jsonify([dict(user) for user in users])

    finally:
        connection.close()


# =====================================
# START APPLICATION
# =====================================

if __name__ == "__main__":
    initialize_database()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
