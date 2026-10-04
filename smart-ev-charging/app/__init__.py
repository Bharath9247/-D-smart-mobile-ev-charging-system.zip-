from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

from config import Config

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # --- Blueprints ------------------------------------------------------
    from app.auth.routes import auth_bp
    from app.user.routes import user_bp
    from app.admin.routes import admin_bp
    from app.driver.routes import driver_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(driver_bp, url_prefix="/driver")

    from flask import redirect, url_for
    from flask_login import current_user

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            if current_user.role == "driver":
                return redirect(url_for("driver.dashboard"))
            return redirect(url_for("user.dashboard"))
        return redirect(url_for("auth.login"))

    with app.app_context():
        db.create_all()
        _seed_defaults()

    return app


def _seed_defaults():
    """Create default charging price tiers and a demo admin on first run."""
    from app.models import ChargingPrice, User

    if not ChargingPrice.query.first():
        for ctype, price, fee in [
            ("AC-Slow", 8.0, 30.0),
            ("AC-Fast", 12.0, 50.0),
            ("DC-Fast", 18.0, 80.0),
        ]:
            db.session.add(ChargingPrice(charging_type=ctype, price_per_kwh=price, service_fee=fee))

    if not User.query.filter_by(role="admin").first():
        admin = User(name="System Admin", email="admin@evcharge.local", role="admin")
        admin.set_password("Admin@123")
        db.session.add(admin)

    db.session.commit()
