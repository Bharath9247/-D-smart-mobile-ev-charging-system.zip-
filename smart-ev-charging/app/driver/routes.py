from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from app import db
from app.models import ChargingVan, ChargingRequest, Payment, Notification
from app.utils import roles_required

driver_bp = Blueprint("driver", __name__)


@driver_bp.before_request
@login_required
def _guard():
    pass


def _my_van():
    return ChargingVan.query.filter_by(driver_id=current_user.id).first()


@driver_bp.route("/dashboard")
@roles_required("driver")
def dashboard():
    van = _my_van()
    active_request = None
    if van:
        active_request = ChargingRequest.query.filter(
            ChargingRequest.van_id == van.id,
            ChargingRequest.status.in_(["assigned", "en_route", "charging"])
        ).first()
    return render_template("driver/dashboard.html", van=van, active_request=active_request,
                            maps_key=current_app.config["GOOGLE_MAPS_API_KEY"])


@driver_bp.route("/add-van", methods=["POST"])
@roles_required("driver")
def add_van():
    """Self-service van registration for a driver who has no van assigned yet."""
    if _my_van():
        flash("You already have a van assigned.", "warning")
        return redirect(url_for("driver.dashboard"))

    van_number = request.form.get("van_number", "").strip()
    if not van_number:
        flash("Van number is required.", "danger")
        return redirect(url_for("driver.dashboard"))

    if ChargingVan.query.filter_by(van_number=van_number).first():
        flash("That van number is already registered.", "danger")
        return redirect(url_for("driver.dashboard"))

    battery = float(request.form.get("battery_capacity_kwh", 50) or 50)
    supported = request.form.getlist("supported_types") or ["AC-Slow", "AC-Fast", "DC-Fast"]
    lat = request.form.get("lat")
    lng = request.form.get("lng")

    van = ChargingVan(
        van_number=van_number,
        driver_id=current_user.id,
        battery_capacity_kwh=battery,
        supported_types=",".join(supported),
        status="offline",
        current_lat=float(lat) if lat else None,
        current_lng=float(lng) if lng else None,
    )
    db.session.add(van)
    db.session.commit()

    flash(f"Van {van_number} registered to your account. Go online when you're ready for requests.", "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/requests")
@roles_required("driver")
def my_requests():
    van = _my_van()
    reqs = []
    if van:
        reqs = ChargingRequest.query.filter_by(van_id=van.id).order_by(
            ChargingRequest.requested_at.desc()).all()
    return render_template("driver/requests.html", reqs=reqs, van=van)


@driver_bp.route("/toggle-availability", methods=["POST"])
@roles_required("driver")
def toggle_availability():
    van = _my_van()
    if not van:
        flash("No van assigned to your account yet. Contact admin.", "warning")
        return redirect(url_for("driver.dashboard"))
    van.status = "available" if van.status == "offline" else "offline"
    db.session.commit()
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/update-location", methods=["POST"])
@roles_required("driver")
def update_location():
    """Called periodically by the driver app's GPS watcher (HTML5 Geolocation)."""
    van = _my_van()
    if not van:
        return jsonify({"error": "no van"}), 404
    data = request.get_json(silent=True) or {}
    van.current_lat = float(data.get("lat"))
    van.current_lng = float(data.get("lng"))
    van.last_updated = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@driver_bp.route("/request/<int:request_id>/navigate")
@roles_required("driver")
def navigate(request_id):
    van = _my_van()
    req = ChargingRequest.query.filter_by(id=request_id, van_id=van.id if van else -1).first_or_404()
    req.status = "en_route"
    db.session.commit()
    return render_template("driver/navigate.html", req=req,
                            maps_key=current_app.config["GOOGLE_MAPS_API_KEY"])


@driver_bp.route("/request/<int:request_id>/start", methods=["POST"])
@roles_required("driver")
def start_charging(request_id):
    van = _my_van()
    req = ChargingRequest.query.filter_by(id=request_id, van_id=van.id if van else -1).first_or_404()
    req.status = "charging"
    req.started_at = datetime.utcnow()
    db.session.commit()

    db.session.add(Notification(user_id=req.user_id,
                                 message=f"Charging started for request #{req.id}."))
    db.session.commit()
    flash("Charging session started.", "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/request/<int:request_id>/end", methods=["POST"])
@roles_required("driver")
def end_charging(request_id):
    van = _my_van()
    req = ChargingRequest.query.filter_by(id=request_id, van_id=van.id if van else -1).first_or_404()
    req.status = "completed"
    req.ended_at = datetime.utcnow()
    van.status = "available"
    db.session.commit()

    db.session.add(Notification(user_id=req.user_id,
                                 message=f"Charging complete for request #{req.id}. Amount due: ₹{req.amount}"))
    db.session.commit()
    flash("Charging session ended.", "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/request/<int:request_id>/status", methods=["POST"])
@roles_required("driver")
def upload_status(request_id):
    """Free-text/progress status update the driver can push mid-session."""
    van = _my_van()
    req = ChargingRequest.query.filter_by(id=request_id, van_id=van.id if van else -1).first_or_404()
    note = request.form.get("note", "").strip()
    if note:
        db.session.add(Notification(user_id=req.user_id, message=f"Update on request #{req.id}: {note}"))
        db.session.commit()
    flash("Status update sent to customer.", "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/request/<int:request_id>/collect-payment", methods=["POST"])
@roles_required("driver")
def collect_payment(request_id):
    """Driver records a cash/offline card payment collected on-site."""
    van = _my_van()
    req = ChargingRequest.query.filter_by(id=request_id, van_id=van.id if van else -1).first_or_404()

    payment = req.payment or Payment(request_id=req.id)
    payment.amount = req.amount
    payment.method = request.form.get("method", "cash")
    payment.provider = "offline"
    payment.status = "success"
    payment.paid_at = datetime.utcnow()
    db.session.add(payment)
    db.session.commit()

    flash("Offline payment recorded.", "success")
    return redirect(url_for("driver.dashboard"))
