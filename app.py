from flask import Flask, render_template, request, redirect, url_for
from PIL import Image
import os

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

if __name__ == '__main__':
    app.run(debug=True, port=5500)