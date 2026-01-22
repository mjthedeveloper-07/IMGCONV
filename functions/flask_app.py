# functions/flask_app.py
from werkzeug.serving import run_simple
from app import app

def handler(event, context):
    return run_simple('0.0.0.0', 5000, app, use_reloader=True, use_debugger=True)
