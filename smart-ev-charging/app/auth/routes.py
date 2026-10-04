import jwt
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        if role not in ("user", "driver"):
            role = "user"  # admins are never self-registered

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("auth.register"))

        u = User(name=name, email=email, phone=phone, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            if user.role == "driver":
                return redirect(url_for("driver.dashboard"))
            return redirect(url_for("user.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# JWT API endpoint — for a future mobile app / SPA client.
# Web pages above use Flask-Login sessions; this issues stateless tokens
# for API consumers as called out in the tech stack (JWT auth).
# ---------------------------------------------------------------------------
@auth_bp.route("/api/token", methods=["POST"])
def api_token():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    payload = {
        "sub": user.id,
        "role": user.role,
        "exp": datetime.utcnow() + current_app.config["JWT_EXP_DELTA"],
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")
    return jsonify({"access_token": token, "role": user.role})
