# BUSINESS Domain entrypoint (after domain split)
# PYTHONPATH must include both apps/ and libs/ directories
web: PYTHONPATH=/app uvicorn apps.business.main:app --host 0.0.0.0 --port $PORT
