
import os
import subprocess
import sys

# Collect files before WhiteNoise starts serving requests.
project_root = os.path.dirname(os.path.abspath(__file__))
subprocess.run(
    [sys.executable, os.path.join(project_root, "manage.py"), "collectstatic", "--noinput"],
    cwd=project_root,
    check=True,
)
os.chdir(project_root)

# Hosting ka PORT read karo
port = os.environ.get("PORT", "8000")
workers = "2"
threads = "2"

# Python ke through Gunicorn start karo
os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "gunicorn",
        "--workers",
        workers,
        "--threads",
        threads,
        "--bind",
        f"0.0.0.0:{port}",
        "ramjicart.wsgi:application",
    ],
)
