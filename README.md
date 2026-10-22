# Ramjicart Django backend

Django serves the existing HTML pages and handles customer, restaurant, and
delivery-partner accounts, cart/checkout, order hand-off, and 4-digit
confirmation codes. Payment gateway integration is intentionally disabled for
now. The order pages show the payable amount and whether payment is due at the
restaurant or on delivery.

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

Restaurant discovery asks customers for their city and six-digit PIN code,
with optional nearby landmark and market. Results are limited to restaurants
matching the supplied city or PIN code, then ranked by exact landmark, market,
PIN code, and city matches in that order. This is text-based matching, not a
GPS distance or delivery-radius calculation.

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
applicable delivery and platform fees only; it deliberately excludes the
restaurant's payout. The payment gateway is not connected, so no online
payment is collected yet.

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
