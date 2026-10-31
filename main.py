
import os

# Hosting ka PORT environment variable
port = os.environ.get("PORT", "8000")

# Django application ko Gunicorn se start karo
os.execvp(
    "gunicorn",
    [
        "gunicorn",
        "--bind",
        f"0.0.0.0:{port}",
        "ramjicart.wsgi:application",
    ],
)
