from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import User, ChargingVan, ChargingRequest, ChargingPrice, Payment
from app.utils import roles_required, find_nearest_available_van, calculate_amount

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
@login_required
def _guard():
    pass


@admin_bp.route("/dashboard")
@roles_required("admin")
def dashboard():
    stats = {
        "total_users": User.query.filter_by(role="user").count(),
        "total_drivers": User.query.filter_by(role="driver").count(),
        "total_vans": ChargingVan.query.count(),
        "pending_requests": ChargingRequest.query.filter_by(status="pending").count(),
        "active_requests": ChargingRequest.query.filter(
            ChargingRequest.status.in_(["assigned", "en_route", "charging"])).count(),
        "completed_today": ChargingRequest.query.filter(
            ChargingRequest.status == "completed",
            func.date(ChargingRequest.ended_at) == datetime.utcnow().date()).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)



@admin_bp.route("/users")
@roles_required("admin")
def manage_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/<int:user_id>/set-role", methods=["POST"])
@roles_required("admin")
def set_role(user_id):
    """Set any user's role to user / driver / admin (used to add more admins)."""
    u = User.query.get_or_404(user_id)
    new_role = request.form.get("role")

    if new_role not in ("user", "driver", "admin"):
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.manage_users"))

    if u.role == "admin" and new_role != "admin" and User.query.filter_by(role="admin").count() <= 1:
        flash("You can't remove the last remaining admin.", "danger")
        return redirect(url_for("admin.manage_users"))

    u.role = new_role
    db.session.commit()
    flash(f"{u.name}'s role updated to {u.role}.", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/users/add-admin", methods=["POST"])
@roles_required("admin")
def add_admin():
    """Create a brand-new admin account directly from the admin panel."""
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not (name and email and password):
        flash("Name, email, and password are all required.", "danger")
        return redirect(url_for("admin.manage_users"))

    if User.query.filter_by(email=email).first():
        flash("An account with that email already exists.", "danger")
        return redirect(url_for("admin.manage_users"))

    new_admin = User(name=name, email=email, role="admin")
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()

    flash(f"New admin account created for {email}.", "success")
    return redirect(url_for("admin.manage_users"))



@admin_bp.route("/vans", methods=["GET", "POST"])
@roles_required("admin")
def manage_vans():
    if request.method == "POST":
        van_number = request.form["van_number"]
        driver_id = request.form.get("driver_id") or None
        battery = float(request.form.get("battery_capacity_kwh", 50))
        van = ChargingVan(van_number=van_number, driver_id=driver_id,
                           battery_capacity_kwh=battery, status="offline")
        db.session.add(van)
        db.session.commit()
        flash("Van added.", "success")
        return redirect(url_for("admin.manage_vans"))

    vans = ChargingVan.query.all()
    unassigned_drivers = User.query.filter_by(role="driver").all()
    return render_template("admin/vans.html", vans=vans, drivers=unassigned_drivers)


@admin_bp.route("/requests")
@roles_required("admin")
def manage_requests():
    pending = ChargingRequest.query.filter_by(status="pending").order_by(
        ChargingRequest.requested_at).all()
    vans = ChargingVan.query.filter_by(status="available").all()
    return render_template("admin/requests.html", pending=pending, vans=vans)


@admin_bp.route("/requests/<int:request_id>/assign", methods=["POST"])
@roles_required("admin")
def assign_request(request_id):
    req = ChargingRequest.query.get_or_404(request_id)
    van_id = request.form.get("van_id")

    if van_id:
        van = ChargingVan.query.get_or_404(van_id)
    else:
        # auto-assign nearest available van (placeholder for the ML dispatch model)
        van = find_nearest_available_van(ChargingVan.query.all(), req.lat, req.lng)

    if not van:
        flash("No available van to assign.", "danger")
        return redirect(url_for("admin.manage_requests"))

    req.van_id = van.id
    req.status = "assigned"
    req.assigned_at = datetime.utcnow()
    van.status = "busy"
    db.session.commit()

    flash(f"Request #{req.id} assigned to van {van.van_number}.", "success")
    return redirect(url_for("admin.manage_requests"))



@admin_bp.route("/monitor")
@roles_required("admin")
def monitor():
    vans = ChargingVan.query.all()
    return render_template("admin/monitor.html", vans=vans,
                            maps_key=current_app.config["GOOGLE_MAPS_API_KEY"])


@admin_bp.route("/api/van-locations")
@roles_required("admin")
def api_van_locations():
    vans = ChargingVan.query.all()
    return jsonify([{
        "id": v.id, "van_number": v.van_number, "status": v.status,
        "lat": v.current_lat, "lng": v.current_lng,
    } for v in vans])



@admin_bp.route("/revenue")
@roles_required("admin")
def revenue():
    total_revenue = db.session.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.status == "success").scalar()
    by_type = (db.session.query(ChargingRequest.charging_type,
                                 func.coalesce(func.sum(Payment.amount), 0.0))
               .join(Payment, Payment.request_id == ChargingRequest.id)
               .filter(Payment.status == "success")
               .group_by(ChargingRequest.charging_type).all())
    recent_payments = (Payment.query.filter_by(status="success")
                        .order_by(Payment.paid_at.desc()).limit(20).all())
    return render_template("admin/revenue.html", total_revenue=total_revenue,
                            by_type=by_type, recent_payments=recent_payments)



@admin_bp.route("/prices", methods=["GET", "POST"])
@roles_required("admin")
def manage_prices():
    if request.method == "POST":
        for price in ChargingPrice.query.all():
            key_rate = f"rate_{price.id}"
            key_fee = f"fee_{price.id}"
            if key_rate in request.form:
                price.price_per_kwh = float(request.form[key_rate])
                price.service_fee = float(request.form[key_fee])
        db.session.commit()
        flash("Pricing updated.", "success")
        return redirect(url_for("admin.manage_prices"))

    prices = ChargingPrice.query.all()
    return render_template("admin/prices.html", prices=prices)
