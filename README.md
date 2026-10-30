# DeliveryCart

This repository contains the Django API and the Cloudflare-hosted frontend.

## Project layout

- `backend/` — Django project, API, migrations, templates, and Python dependencies.
- `frontend/` — vinext/Workers configuration and existing HTML, JavaScript, and static assets in `frontend/public/`.

See `backend/README.md` for Django setup and `frontend/README.md` for frontend
development and Cloudflare build commands.

## Local development

Start these in separate PowerShell terminals.

### Django API

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Set a private local DJANGO_SECRET_KEY in backend/.env.
# Keep DATABASE_URL blank in backend/.env to use its local SQLite database.
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### Frontend

```powershell
Set-Location frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend proxies `/api/` and `/media/` to
the Django server at `http://127.0.0.1:8000`. The frontend `.env.local` must
keep `NEXT_PUBLIC_API_URL` set to that backend origin. The default local CORS
and CSRF origins in `backend/.env.example` include the Vite port `5173`.

Check the backend directly with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/config/public
```

Then check through the frontend proxy with:

```powershell
Invoke-RestMethod http://127.0.0.1:5173/api/config/public
```

Both should return the public client configuration JSON. Keep real credentials
in local environment files or the hosting provider's environment settings.
