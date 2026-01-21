from flask import Flask, render_template, request, redirect, url_for, jsonify
from PIL import Image
import os

app = Flask(__name__)

# Ensure the 'static/images' directory exists
if not os.path.exists('static/images'):
    os.makedirs('static/images')

def recommend_settings(prompt):
    prompt_text = (prompt or "").strip().lower()
    recommendations = [
        {
            "keywords": ["animation", "gif"],
            "format": "GIF",
            "quality": 90,
            "reason": "Keeps animation support for lively content.",
        },
        {
            "keywords": ["icon", "favicon"],
            "format": "ICO",
            "quality": 90,
            "reason": "Sized for favicons and app icons.",
        },
        {
            "keywords": ["pdf", "document"],
            "format": "PDF",
            "quality": 100,
            "reason": "Ideal for document-style outputs.",
        },
        {
            "keywords": ["print", "poster", "high quality"],
            "format": "TIFF",
            "quality": 100,
            "reason": "Lossless quality for print-ready work.",
        },
        {
            "keywords": ["transparent", "logo"],
            "format": "PNG",
            "quality": 100,
            "reason": "Preserves transparency for logos and graphics.",
        },
        {
            "keywords": ["photo", "portrait"],
            "format": "JPEG",
            "quality": 85,
            "reason": "Balanced compression for photography.",
        },
        {
            "keywords": ["web", "website", "fast", "small", "optimize"],
            "format": "WEBP",
            "quality": 80,
            "reason": "Smaller size with strong quality for the web.",
        },
    ]
    for recommendation in recommendations:
        if any(keyword in prompt_text for keyword in recommendation["keywords"]):
            return recommendation
    return {
        "format": "PNG",
        "quality": 90,
        "reason": "A crisp default for most visuals.",
    }

@app.route('/')
def index():
    return render_template("index.html")

@app.route("/prompt-enhance", methods=["POST"])
def prompt_enhance():
    data = request.get_json(silent=True) or {}
    suggestion = recommend_settings(data.get("prompt", ""))
    return jsonify(
        {
            "format": suggestion["format"],
            "quality": suggestion["quality"],
            "reason": suggestion["reason"],
        }
    )

@app.route("/convert", methods=["POST", "GET"])
def convert():
    if request.method == "POST":
        file = request.files["image"]
        format = request.form.get("format")
        quality_value = request.form.get("quality", "").strip()
        quality = None
        if quality_value:
            try:
                quality = int(quality_value)
            except ValueError:
                quality = None
        outputimage, ext = os.path.splitext(file.filename)
        format = format.lower()
        outputimage = outputimage + "." + format
        output_path = os.path.join('static/images', outputimage)
        
        with Image.open(file) as image:
            save_kwargs = {}
            if quality is not None and format in {"jpeg", "webp"}:
                quality = max(40, min(100, quality))
                save_kwargs["quality"] = quality
                if format == "jpeg":
                    save_kwargs["optimize"] = True
            image.save(output_path, format=format.upper(), **save_kwargs)
        
        image_url = url_for('static', filename='images/' + outputimage)
        return render_template("convert.html", image_url=image_url)

    return redirect("/")

if __name__ == '__main__':
    app.run(debug=True, port=5500)
