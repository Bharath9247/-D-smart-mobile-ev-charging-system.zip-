import math
from functools import wraps
from flask import abort
from flask_login import current_user


def roles_required(*roles):
    """Restrict a view to one or more user roles, e.g. @roles_required('admin')."""
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two GPS points, in kilometres."""
    if None in (lat1, lng1, lat2, lng2):
        return float("inf")
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def find_nearest_available_van(vans, lat, lng):
    """
    Simple nearest-van assignment heuristic.
    Stands in for the 'Route Prediction & Demand Forecasting (ML)' item in the
    tech stack — this is a distance-based placeholder that a trained model
    (e.g. scikit-learn regressor on historical demand + traffic) can later replace.
    """
    candidates = [v for v in vans if v.status == "available"]
    if not candidates:
        return None
    return min(candidates, key=lambda v: haversine_km(lat, lng, v.current_lat, v.current_lng))


def estimate_eta_minutes(lat1, lng1, lat2, lng2, avg_speed_kmh=30):
    dist = haversine_km(lat1, lng1, lat2, lng2)
    if dist == float("inf"):
        return None
    return round((dist / avg_speed_kmh) * 60, 1)


def calculate_amount(charging_type, estimated_kwh, price_table):
    """price_table: dict {charging_type: ChargingPrice}"""
    price = price_table.get(charging_type)
    if not price:
        return 0.0
    return round(price.price_per_kwh * estimated_kwh + price.service_fee, 2)
