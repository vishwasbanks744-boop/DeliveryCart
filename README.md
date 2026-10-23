# Ramjicart Django backend

Django serves the existing HTML pages and handles customer, restaurant, and
delivery-partner accounts, cart/checkout, order hand-off, and 4-digit
confirmation codes. Cashfree hosted checkout is implemented and stays disabled
until Cashfree credentials are configured. The order pages show the fee amount
collected online and the remaining amount due at handover.

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DJANGO_SECRET_KEY = "replace-with-a-long-random-secret"
$env:DJANGO_DEBUG = "True"
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Visitors go to login first. Customer registration
is at `/register.html`; restaurant registration is at
`/resturentregisterpage.html`; delivery-partner registration is at
`/deliveryregister.html`. After a customer logs in, the homepage opens.
Restaurant and delivery-partner accounts need admin approval before their
dashboards can access orders.

Approved restaurants can open their partnership certificate from the
restaurant dashboard. The certificate includes its generated registration
number, approval issue date, CEO details, and a QR code that opens a public
verification page. Certificates are not issued while an account is awaiting
admin approval; revoked or unapproved certificates show as not verified.

Restaurant discovery supports either browser GPS or the existing city and
six-digit PIN-code search, with optional nearby landmark and market. GPS
results with saved restaurant coordinates are ranked by straight-line distance;
restaurants without coordinates remain available after geocoded results. The
city/PIN fallback keeps its landmark, market, PIN-code, and city ranking.
Straight-line distance is not a driving route or a delivery-radius guarantee.

## Authentication and live delivery location

Customer, restaurant, and delivery registration and login are exposed through
the role-specific `/api/auth/*`, `/api/restaurant/register`, and
`/api/delivery/register` endpoints. By default, the UI uses Django passwords
and sessions through `static/js/auth-client.js`. To enable Firebase Email and
Password or Google sign-in, configure the Firebase web settings and server
service account in environment variables from `.env.example`, install
requirements, then set `FIREBASE_AUTH_ENABLED=True`. Enable Email/Password and
Google providers in Firebase Authentication. Google sign-in is available on
customer, restaurant, and delivery login and registration pages. Registration
still collects each role's required profile details; Google provides the email
and account identity. Login sends a Firebase ID token to Django, which verifies
it and creates the usual Django session. Cart, orders, restaurant, and delivery
APIs remain session-based. Firebase verification follows the client SDK
sign-in and server Admin SDK ID-token verification pattern in the [Firebase web guide](https://firebase.google.com/docs/auth/web/start)
and [Firebase Admin guide](https://firebase.google.com/docs/auth/admin/verify-id-tokens).
Never commit the service account credential.

Restaurants can save their location from registration or their profile, and a
customer can optionally share a delivery destination at checkout. Coordinates
are validated and stored with the restaurant/order; the browser GPS permission
is requested only after the user presses the location button. Customer
discovery and the homepage can rank geocoded restaurants by straight-line
distance. Existing city/PIN search and text-only delivery addresses remain
supported. Browser location, Google Maps URLs, the optional interactive map
loader, and marker rendering are kept behind `static/js/maps-client.js`.

When a delivery partner is on the way, they can start or stop location sharing
from their delivery dashboard. Sharing also makes them eligible to see and
accept available offers. Each ready delivery order is shown to all approved
delivery partners; accepting requires a recent GPS fix and a restaurant
location within `DELIVERY_DISPATCH_RADIUS_KM` (10 km by default). If no nearby
partner is sharing location, the order remains ready and open on the
restaurant and delivery dashboards. Offers outside the viewing partner's
radius hide the customer's contact and delivery details. Customers can open a
live location and route in Google Maps; an interactive tracking map loads when
`GOOGLE_MAPS_API_KEY` is configured. The Maps key is sent to browsers, so
restrict it by website referrer in Google Cloud. The Maps loader uses Google's
[dynamic library import](https://developers.google.com/maps/documentation/javascript/load-maps-js-api).
Browser location sharing requires HTTPS (localhost is allowed) and explicit
location permission. Straight-line distance is not used as a delivery-fee
quote.

Food and restaurant photos are supplied by restaurant data. Missing or failed
food images use the local `/static/food-placeholder.svg` illustration. Food
categories use built-in emoji tiles, so they do not rely on brittle remote
image URLs.

Public legal information is available at `/terms.html` and `/privacy.html`;
both pages are linked from the customer registration form and homepage.

## Admin setup

1. Sign in to `/admin/` with the Django superuser.
2. Review new restaurant accounts in **Account profiles** and **Restaurants**.
   Approve both the account profile and restaurant record.
3. Review and approve delivery-partner account profiles.
4. Create food categories and menu items in **Foods**, assigning each item to
   an approved restaurant, or add them from the restaurant dashboard's menu
   form (product pictures use a public HTTP/HTTPS image URL).
5. Set each restaurant's current commission and approved maximum commission
   percentage. The current percentage cannot exceed the approved maximum.
6. Edit **Marketplace pricing** to change the delivery charge. Delivery orders
   also include the fixed ₹10 platform fee; pickup orders do not.

Commission is calculated from food subtotal with a ₹1 minimum and is deducted
from the restaurant's share. Orders keep a snapshot of all prices and fees.
The checkout quote exposes `gatewayAmount` as restaurant commission plus
applicable delivery and platform fees only. The rest of the food subtotal is
paid at handover (to the delivery partner for delivery orders, or the
restaurant for pickup). Cashfree hosted checkout, server-side payment checks,
and signed webhooks are implemented. They remain disabled until Cashfree
credentials and a public HTTPS webhook URL are configured.

To enable Cashfree sandbox payments, set `CASHFREE_ENABLED=True`,
`CASHFREE_ENVIRONMENT=sandbox`, and the sandbox `CASHFREE_APP_ID` and
`CASHFREE_SECRET_KEY` in the deployment environment. Configure the webhook URL
`https://<your-domain>/api/payments/cashfree/webhook` in Cashfree for payment
success events. Use the same Cashfree account/environment for the API keys and
webhook. After sandbox checkout and webhook verification, switch to production
credentials and `CASHFREE_ENVIRONMENT=production`. Never put the secret key in
browser code or commit it to the repository. Cashfree collects the fee-only
amount; this integration does not automatically transfer the remaining amount
to a restaurant or delivery partner.

## Order process

- Customer adds food from one restaurant to the cart, chooses **Pickup (on the
  way)** or **Delivery**, and places the order.
- New orders appear in that restaurant's order panel. Restaurant staff accept,
  start preparing, and mark the order ready. The restaurant dashboard combines
  this order panel with the menu-item form; the old orders-page link opens the
  same dashboard at its orders section.
- For **Pickup/on-the-way**, the customer goes to the restaurant. The customer
  order page shows a 4-digit code; restaurant staff enter it to confirm pickup
  and complete the order.
- For **Delivery**, a delivery partner accepts restaurant-ready orders,
  confirms pickup and delivery status per order, and enters that customer's
  4-digit code at handover. Partners can hold multiple active deliveries; each
  order has its own status controls and confirmation-code field. The delivery
  dashboard shows the restaurant's net payout (food subtotal minus restaurant
  commission), not the customer's gross total, on each delivery. The partner
  dashboard includes available orders, active deliveries, completed-delivery
  history, refresh, and sign-out controls. Earnings are not tracked while
  payment processing is off. A correct code completes that order.
- Customers can see their own order status and confirmation code. Restaurant
  and delivery APIs never return that code.

## Tests

```powershell
python manage.py test orders
```

Before public deployment, use HTTPS, a production database such as PostgreSQL,
a production `DJANGO_SECRET_KEY`, and configure secure allowed hosts.

## Deploy to Render

1. Push this project to a Git repository and create a **Blueprint** in Render
   from that repository. Render reads `render.yaml` to create the Django web
   service and PostgreSQL database. `.python-version` selects the latest
   Python 3.13 patch release for Render.
2. Keep `DJANGO_DEBUG=False` and the generated `DJANGO_SECRET_KEY` in the
   Render environment. The app automatically trusts its Render hostname for
   host and CSRF checks. If you add a custom domain, add it to
   `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` (the latter as an
   `https://` origin).
3. The build installs dependencies and collects static files; the pre-deploy
   step applies database migrations. Create an administrator after the first
   deployment with a Render shell using `python manage.py createsuperuser`.
4. Restaurant logo uploads are stored on the blueprint's persistent disk and
   served from that disk. Render persistent disks require a paid web service
   and are mounted at `/opt/render/project/src/media`; do not remove this disk
   unless uploads are moved to a separate persistent object-storage service.

The Blueprint provisions a paid starter web service, a 1 GB persistent media
disk, and a basic PostgreSQL database. Review Render's current pricing before
creating the Blueprint. For local development, SQLite remains the default
when `DATABASE_URL` is not set and `DJANGO_DEBUG=True`.

The new PostgreSQL database starts empty. Existing records in the local
`db.sqlite3` and files in a local `media/` directory are not copied to Render;
export/import any data you need to preserve before switching production traffic.
