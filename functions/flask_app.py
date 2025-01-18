# functions/flask_app.py
from flask import Flask, jsonify, render_template, request, redirect, url_for
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
import os
from PIL import Image

app = Flask(__name__)

# Ensure the 'static/images' directory exists
if not os.path.exists('static/images'):
    os.makedirs('static/images')

@app.route('/')
def index():
    return render_template("index.html")

@app.route("/convert", methods=["POST", "GET"])
def convert():
    if request.method == "POST":
        file = request.files["image"]
        format = request.form.get("format")
        outputimage, ext = os.path.splitext(file.filename)
        format = format.lower()
        outputimage = outputimage + "." + format
        output_path = os.path.join('static/images', outputimage)
        
        with Image.open(file) as image:
            image.save(output_path, format=format.upper())
        
        image_url = url_for('static', filename='images/' + outputimage)
        return render_template("convert.html", image_url=image_url)

    return redirect("/")

def handler(event, context):
    return run_simple('0.0.0.0', 5000, app, use_reloader=True, use_debugger=True)