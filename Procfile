release: python manage.py collectstatic --noinput
web: gunicorn ramjicart.wsgi:application --workers 2 --threads 2 --bind 0.0.0.0:$PORT
