web: gunicorn -k uvicorn.workers.UvicornWorker backend.main:app --bind 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile -
