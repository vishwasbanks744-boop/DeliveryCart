
import os
import sys

# Hosting ka PORT read karo
port = os.environ.get("PORT", "8000")

# Python ke through Gunicorn start karo
os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "gunicorn",
        "--bind",
        f"0.0.0.0:{port}",
        "ramjicart.wsgi:application",
    ],
)
