from datetime import datetime
from flask_login import UserMixin
from app import db, bcrypt, login_manager


# ---------------------------------------------------------------------------
# USER  (covers User / Admin / Driver — differentiated by `role`)
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # user | admin | driver
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    requests = db.relationship("ChargingRequest", backref="customer", lazy=True,
                                foreign_keys="ChargingRequest.user_id")
    van = db.relationship("ChargingVan", backref="driver", uselist=False,
                           foreign_keys="ChargingVan.driver_id")
    notifications = db.relationship("Notification", backref="user", lazy=True)

    def set_password(self, raw_password):
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# CHARGING VAN  (mobile charging unit operated by a driver)
# ---------------------------------------------------------------------------
class ChargingVan(db.Model):
    __tablename__ = "charging_vans"

    id = db.Column(db.Integer, primary_key=True)
    van_number = db.Column(db.String(50), unique=True, nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(db.String(20), default="offline")  # offline | available | busy
    current_lat = db.Column(db.Float)
    current_lng = db.Column(db.Float)
    battery_capacity_kwh = db.Column(db.Float, default=50.0)
    supported_types = db.Column(db.String(120), default="AC-Slow,AC-Fast,DC-Fast")
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    requests = db.relationship("ChargingRequest", backref="van", lazy=True)

    def __repr__(self):
        return f"<Van {self.van_number} ({self.status})>"


# ---------------------------------------------------------------------------
# CHARGING PRICE  (admin-managed price list per charging type)
# ---------------------------------------------------------------------------
class ChargingPrice(db.Model):
    __tablename__ = "charging_prices"

    id = db.Column(db.Integer, primary_key=True)
    charging_type = db.Column(db.String(50), unique=True, nullable=False)
    price_per_kwh = db.Column(db.Float, nullable=False, default=10.0)
    service_fee = db.Column(db.Float, nullable=False, default=50.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# CHARGING REQUEST  (core booking entity)
# ---------------------------------------------------------------------------
class ChargingRequest(db.Model):
    __tablename__ = "charging_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    van_id = db.Column(db.Integer, db.ForeignKey("charging_vans.id"), nullable=True)

    charging_type = db.Column(db.String(50), nullable=False)  # AC-Slow / AC-Fast / DC-Fast
    vehicle_number = db.Column(db.String(30))
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    address_text = db.Column(db.String(255))

    status = db.Column(db.String(20), default="pending")
    # pending -> assigned -> en_route -> charging -> completed / cancelled

    estimated_kwh = db.Column(db.Float, default=10.0)
    amount = db.Column(db.Float, default=0.0)

    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)

    payment = db.relationship("Payment", backref="request", uselist=False)

    def __repr__(self):
        return f"<Request #{self.id} {self.status}>"


# ---------------------------------------------------------------------------
# PAYMENT
# ---------------------------------------------------------------------------
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("charging_requests.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(20), default="online")  # online | cash | card (offline)
    provider = db.Column(db.String(20), default="stripe")  # stripe | razorpay | offline
    transaction_id = db.Column(db.String(120))
    status = db.Column(db.String(20), default="pending")  # pending | success | failed
    paid_at = db.Column(db.DateTime)


# ---------------------------------------------------------------------------
# NOTIFICATION
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
