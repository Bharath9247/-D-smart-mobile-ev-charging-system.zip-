# Smart Mobile EV Charging System

A full-stack web application that connects EV owners with **mobile charging vans**.
Users request on-demand charging at their current location, admins dispatch the
nearest available van, and drivers navigate, charge, and collect payment.

Built to match the requested feature set (User / Admin / Driver modules) and
technology stack (Flask, MySQL/PostgreSQL, Google Maps, JWT, Stripe/Razorpay).

Maps ship in **demo mode out of the box**: every map screen (admin live
monitor, user request/track, driver navigate) uses Leaflet + OpenStreetMap
tiles and the free OSRM public routing server, so no API key or billing setup
is needed to see it working. See §5 for swapping in real Google Maps later.

---

## 1. Features implemented

| Module | Features |
|---|---|
| **User** | Register/Login, request mobile charging, GPS auto-detect (HTML5 Geolocation), select charging type (AC-Slow / AC-Fast / DC-Fast), live van tracking, online payment (simulated Stripe), booking history, in-app notifications |
| **Admin** | Manage users (promote user ↔ driver), manage charging vans, assign requests (manual or auto nearest-van), monitor live van locations on a map, revenue reports (by type + recent payments), manage charging prices |
| **Driver** | Receive assigned requests, live GPS push, turn-by-turn navigation (Google Directions), start/end charging session, push status updates to the customer, collect offline (cash/card) payments |

## 2. Technology stack

| Component | Technology used in this project |
|---|---|
| Frontend | HTML5, CSS3, Bootstrap 5, vanilla JavaScript (server-rendered Jinja2 templates) |
| Backend | Python — **Flask** (blueprints: `auth`, `user`, `admin`, `driver`) |
| Database | SQLAlchemy ORM — **SQLite** by default, drop-in switch to **MySQL** or **PostgreSQL** via `DATABASE_URL` |
| Maps | Leaflet + OpenStreetMap tiles, OSRM demo server for routing (works with zero setup — no API key needed); swappable for Google Maps JavaScript API + Directions API if you add a billing-enabled key |
| GPS | HTML5 Geolocation API (browser-side, used by both the user request form and the driver's live-location pusher) |
| Authentication | Session auth via Flask-Login for the web app, **plus** a `/api/token` endpoint that issues **JWT** tokens for a future mobile app/SPA client |
| Payments | Simulated checkout wired for **Stripe**/**Razorpay** — swap the stub in `app/user/routes.py::pay()` for a real `stripe.PaymentIntent` or Razorpay Order call using the keys in `config.py` |
| ML (optional) | `app/utils.py::find_nearest_available_van()` is a distance-based placeholder for the "Route Prediction & Demand Forecasting" model — replace with a trained scikit-learn model without touching the rest of the app |
| Cloud | Designed to deploy as-is on AWS Elastic Beanstalk / Azure App Service / Firebase Hosting + Cloud Run — see §5 |

## 3. Project structure

```
smart-ev-charging/
├── app/
│   ├── __init__.py          # app factory, extension init, seed data
│   ├── models.py            # User, ChargingVan, ChargingRequest, Payment, ChargingPrice, Notification
│   ├── utils.py             # role decorator, haversine distance, ETA, nearest-van dispatch, pricing
│   ├── auth/routes.py        # register, login, logout, JWT token endpoint
│   ├── user/routes.py        # request charging, tracking, history, payment, notifications
│   ├── admin/routes.py       # users, vans, assign, monitor, revenue, prices
│   ├── driver/routes.py      # requests, GPS push, navigate, start/end, status, offline payment
│   ├── templates/            # Jinja2 + Bootstrap templates per module
│   └── static/css/style.css
├── config.py                 # env-driven configuration (DB, API keys, JWT)
├── run.py                    # dev server entry point
├── requirements.txt
└── .env.example
```

## 4. Local setup

```bash
cd smart-ev-charging
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then fill in your API keys
python run.py
```

The app runs at `http://localhost:5000`. A demo admin account is seeded automatically:

```
email:    admin@evcharge.local
password: Admin@123
```

Register a normal account as **"EV Owner (User)"**, and a second as **"Charging Van
Driver"**. As admin, go to **Manage Vans** to add a van and assign it to the driver
account before that driver can go online.

### Switching the database

By default the app uses a local SQLite file (zero setup). To use MySQL or
PostgreSQL instead, set `DATABASE_URL` in `.env`:

```
DATABASE_URL=mysql+pymysql://user:password@localhost/evcharging
DATABASE_URL=postgresql+psycopg2://user:password@localhost/evcharging
```

No code changes are needed — SQLAlchemy handles the dialect switch.

## 5. Notes on the placeholder integrations

- **Maps**: all four map screens (admin monitor, user request-charging, user
  track, driver navigate) run on Leaflet + OpenStreetMap tiles with the free
  OSRM public demo routing server, so they render and draw routes with zero
  configuration. `GOOGLE_MAPS_API_KEY` in `.env`/`config.py` is kept only as an
  optional hook if you'd rather wire the pages back up to the Google Maps
  JavaScript API + Directions API later (enable those APIs in Google Cloud
  Console and swap the `L.map(...)`/`L.tileLayer(...)` calls for
  `google.maps.Map`/`DirectionsService`). Note the OSRM demo server is rate
  limited and not meant for production traffic — self-host OSRM or use a paid
  routing provider before going live.
- **GPS / Geolocation**: browsers only allow `navigator.geolocation` on secure
  contexts — **HTTPS, or `http://localhost`**. If you run the dev server on a
  plain `http://<lan-ip>:5000` (e.g. testing from a phone on the same Wi-Fi),
  the browser will silently block location access. Every GPS-dependent screen
  (request-charging map, driver dashboard, add-van form) now has a manual
  fallback — click the map to drop a pin, or type latitude/longitude directly —
  so the app is fully usable even without a secure GPS context. For real GPS in
  production, deploy behind HTTPS (see §5 below).
- **Payments**: `user/pay.html` and `user/routes.py::pay()` currently *simulate*
  a successful charge so the full flow is demoable without live credentials.
  Replace the simulated block with real Stripe Elements / Razorpay Checkout JS
  plus a server-side `PaymentIntent`/`Order` call using the secret key.
- **Admins**: only one demo admin is seeded on first run. Any existing admin can
  create more from **Manage Users → Add New Admin**, or change any user's role
  (user/driver/admin) with the role dropdown next to their name. The system
  always keeps at least one admin account.
- **JWT vs sessions**: web pages use cookie-based sessions (`Flask-Login`) since
  that's simplest for server-rendered pages. `/api/token` already issues JWTs so
  a future React Native/Flutter driver or user app can authenticate statelessly
  against the same backend.
- **ML dispatch**: `find_nearest_available_van()` is a simple haversine-distance
  heuristic. It's isolated in `utils.py` specifically so it can be swapped for a
  trained demand-forecasting/route-prediction model later without touching the
  route handlers.

## 6. Suggested next steps

- Add Alembic migrations (`Flask-Migrate`) once the schema stabilizes.
- Add rate/coverage-based pricing tiers per city or per van type.
- Push real-time updates via WebSockets (Flask-SocketIO) instead of polling.
- Add automated tests (`pytest`) for the booking → assignment → payment flow.
