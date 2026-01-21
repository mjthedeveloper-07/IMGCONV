QUALITY_MIN = 40
QUALITY_MAX = 100
PROMPT_MAX_LENGTH = 300


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


def build_save_kwargs(image_format, quality_value):
    if quality_value is None:
        return {}
    value = str(quality_value).strip()
    if not value:
        return {}
    try:
        quality = int(value)
    except ValueError:
        return {}
    format_lower = (image_format or "").lower()
    if format_lower not in {"jpeg", "webp"}:
        return {}
    quality = max(QUALITY_MIN, min(QUALITY_MAX, quality))
    save_kwargs = {"quality": quality}
    if format_lower == "jpeg":
        save_kwargs["optimize"] = True
    return save_kwargs
