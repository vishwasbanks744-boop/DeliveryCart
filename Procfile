release: python manage.py collectstatic --noinput
web: gunicorn ramjicart.wsgi:application --bind 0.0.0.0:$PORT
