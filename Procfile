web: gunicorn config.wsgi:application --bind 0.0.0.0:8443 --workers 3 --timeout 120
worker: celery -A config worker --loglevel=info --concurrency=2
