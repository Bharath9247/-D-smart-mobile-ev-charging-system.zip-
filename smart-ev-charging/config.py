import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """
    Central configuration.
    Values are read from environment variables so the same code can run
    against SQLite (dev), MySQL, or PostgreSQL (production) without changes.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
    JWT_EXP_DELTA = timedelta(hours=12)

    # --- Database -----------------------------------------------------
    # Default: local SQLite for zero-setup demo.
    # For MySQL:      mysql+pymysql://user:password@localhost/evcharging
    # For PostgreSQL: postgresql+psycopg2://user:password@localhost/evcharging
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'evcharging.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Third-party services -----------------------------------------
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "YOUR_GOOGLE_MAPS_API_KEY")
    STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "pk_test_placeholder")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_placeholder")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "razorpay_secret_placeholder")

    # Pretend "live" GPS refresh interval used by the front-end poller (ms)
    LIVE_TRACKING_POLL_MS = 5000
