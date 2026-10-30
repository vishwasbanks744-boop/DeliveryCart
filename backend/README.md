# Ramjicart Django backend

Django serves the API and admin for customer, restaurant, and delivery-partner
accounts, cart/checkout, order hand-off, and 4-digit confirmation codes. The
existing certificate issue and verification endpoints still return HTML for
compatibility. Cashfree hosted checkout stays disabled until its credentials
are configured.

## Run locally (Windows PowerShell)

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and replace DJANGO_SECRET_KEY with a private random value.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

For local development, Django loads `backend/.env` first and falls back to the
repo-root `.env`. Keep both private; `.gitignore` excludes them. The frontend
uses the local Vite origin `http://localhost:5173` by default. Keep that exact
origin in `CORS_ALLOWED_ORIGINS` and `DJANGO_CSRF_TRUSTED_ORIGINS`; do not use
`*`. The frontend proxies API requests through its own origin, so leave
`DJANGO_CSRF_COOKIE_DOMAIN` blank. Production media requires
`AWS_STORAGE_BUCKET_NAME`; configure S3 credentials through environment or a
service identity, never source code.

The public API configuration endpoint is `http://127.0.0.1:8000/api/config/public`.
The frontend runs separately. The Django admin is available at `/admin/`.

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

The restaurant panel checks for new orders every 30 seconds while open. Browser
alerts and sound require the restaurant operator to enable them in the panel.
The `process_restaurant_orders` command should run every minute: it cancels a
still-unaccepted order after 15 minutes and retries Cashfree refunds. Configure
the `process_restaurant_orders` command to run once per minute on the hosting
platform, with the same Cashfree environment values as the web service.
Automatic refunds return the amount captured by Cashfree. The same
command permanently deletes completed, cancelled, and failed order records and
their line items once they are older than 15 days. Active orders and orders
with pending payment/refunds are retained; customer accounts, restaurants, and
products are retained.

## Tests

```powershell
python manage.py test orders
```

Before public deployment, use HTTPS, a production database such as PostgreSQL,
a production `DJANGO_SECRET_KEY`, and configure secure allowed hosts.

## AIC Cloud deployment

Set the AIC service's project root to `backend/`, then configure these commands:

```sh
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn ramjicart.wsgi:application --bind 0.0.0.0:8000
```

If AIC cannot set a project root, run equivalent commands from the repository
root with `cd backend &&` before each command.

Set production environment variables in the hosting dashboard. Keep
`DJANGO_DEBUG=False`, configure `DATABASE_URL`, `DJANGO_SECRET_KEY`, allowed
hosts, CORS/CSRF origins, and S3-compatible media storage. The platform's
working-directory, port, scheduler, PostgreSQL, and storage settings must be
confirmed in its dashboard before deployment.
