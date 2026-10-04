from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from app import db
from app.models import ChargingRequest, ChargingVan, ChargingPrice, Payment, Notification
from app.utils import roles_required, find_nearest_available_van, estimate_eta_minutes, calculate_amount

user_bp = Blueprint("user", __name__)


@user_bp.before_request
@login_required
def _guard():
    pass


@user_bp.route("/dashboard")
@roles_required("user")
def dashboard():
    active = (ChargingRequest.query
              .filter(ChargingRequest.user_id == current_user.id,
                      ChargingRequest.status.notin_(["completed", "cancelled"]))
              .order_by(ChargingRequest.requested_at.desc()).first())
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template("user/dashboard.html", active=active, unread_count=unread_count,
                            maps_key=current_app.config["GOOGLE_MAPS_API_KEY"])


@user_bp.route("/request-charging", methods=["GET", "POST"])
@roles_required("user")
def request_charging():
    prices = ChargingPrice.query.all()

    if request.method == "POST":
        lat = float(request.form["lat"])
        lng = float(request.form["lng"])
        charging_type = request.form["charging_type"]
        vehicle_number = request.form.get("vehicle_number", "")
        address_text = request.form.get("address_text", "")
        estimated_kwh = float(request.form.get("estimated_kwh", 10))

        price_table = {p.charging_type: p for p in prices}
        amount = calculate_amount(charging_type, estimated_kwh, price_table)

        req = ChargingRequest(
            user_id=current_user.id, charging_type=charging_type, vehicle_number=vehicle_number,
            lat=lat, lng=lng, address_text=address_text, estimated_kwh=estimated_kwh,
            amount=amount, status="pending",
        )
        db.session.add(req)
        db.session.commit()

        db.session.add(Notification(user_id=current_user.id,
                                     message=f"Charging request #{req.id} received. Looking for a nearby van."))
        db.session.commit()

        flash("Charging request submitted! We'll notify you once a van is assigned.", "success")
        return redirect(url_for("user.track", request_id=req.id))

    return render_template("user/request_charging.html", prices=prices,
                            maps_key=current_app.config["GOOGLE_MAPS_API_KEY"])


@user_bp.route("/track/<int:request_id>")
@roles_required("user")
def track(request_id):
    req = ChargingRequest.query.filter_by(id=request_id, user_id=current_user.id).first_or_404()
    van = ChargingVan.query.get(req.van_id) if req.van_id else None
    eta = None
    if van:
        eta = estimate_eta_minutes(van.current_lat, van.current_lng, req.lat, req.lng)
    return render_template("user/track.html", req=req, van=van, eta=eta,
                            maps_key=current_app.config["GOOGLE_MAPS_API_KEY"],
                            poll_ms=current_app.config["LIVE_TRACKING_POLL_MS"])


@user_bp.route("/api/track/<int:request_id>")
@roles_required("user")
def api_track(request_id):
    """Polled by the tracking page's JS to refresh the van's live position."""
    req = ChargingRequest.query.filter_by(id=request_id, user_id=current_user.id).first_or_404()
    van = ChargingVan.query.get(req.van_id) if req.van_id else None
    return jsonify({
        "status": req.status,
        "van_lat": van.current_lat if van else None,
        "van_lng": van.current_lng if van else None,
        "eta_minutes": estimate_eta_minutes(van.current_lat, van.current_lng, req.lat, req.lng) if van else None,
    })


@user_bp.route("/history")
@roles_required("user")
def history():
    reqs = (ChargingRequest.query.filter_by(user_id=current_user.id)
            .order_by(ChargingRequest.requested_at.desc()).all())
    return render_template("user/history.html", reqs=reqs)


@user_bp.route("/pay/<int:request_id>", methods=["GET", "POST"])
@roles_required("user")
def pay(request_id):
    req = ChargingRequest.query.filter_by(id=request_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        # NOTE: this simulates a successful Stripe/Razorpay charge.
        # Swap this block for a real `stripe.PaymentIntent.create(...)` /
        # Razorpay Orders API call using the keys in config.py.
        payment = req.payment or Payment(request_id=req.id)
        payment.amount = req.amount
        payment.method = "online"
        payment.provider = "stripe"
        payment.transaction_id = f"sim_{datetime.utcnow().timestamp():.0f}"
        payment.status = "success"
        payment.paid_at = datetime.utcnow()
        db.session.add(payment)
        db.session.commit()

        db.session.add(Notification(user_id=current_user.id,
                                     message=f"Payment of ₹{req.amount} for request #{req.id} received."))
        db.session.commit()

        flash("Payment successful!", "success")
        return redirect(url_for("user.history"))

    return render_template("user/pay.html", req=req,
                            stripe_public_key=current_app.config["STRIPE_PUBLIC_KEY"])


@user_bp.route("/notifications")
@roles_required("user")
def notifications():
    notes = (Notification.query.filter_by(user_id=current_user.id)
             .order_by(Notification.created_at.desc()).all())
    for n in notes:
        n.is_read = True
    db.session.commit()
    return render_template("user/notifications.html", notes=notes)
