import os
import io
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pymongo import ReturnDocument

from database import db, create_document
from schemas import Coupon

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Helpers
COUPON_PREFIX = "WBAU10DIC-"


def _get_next_sequence(seq_name: str) -> int:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    counters = db["counters"]
    doc = counters.find_one_and_update(
        {"_id": seq_name},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    # When upserted first time, value might be None before increment; ensure int
    value = doc.get("value") or 1
    return int(value)


def _build_coupon_image(code: str) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont  # lazy import to avoid startup crash if pillow missing
    except Exception:
        raise HTTPException(status_code=503, detail="Image generator unavailable. Please try again later.")

    # Colors
    RED = (216, 43, 43)  # #D82B2B
    CREAM = (255, 246, 237)  # #FFF6ED
    TEXT = (30, 30, 30)  # #1E1E1E

    # Image size
    W, H = 1080, 1350  # Instagram portrait style
    img = Image.new("RGB", (W, H), color=(255, 255, 255))

    draw = ImageDraw.Draw(img)

    # Top red banner
    banner_h = 220
    draw.rectangle([(0, 0), (W, banner_h)], fill=RED)

    # Cream body background
    draw.rectangle([(0, banner_h), (W, H)], fill=CREAM)

    # Title text
    title = "Il MIAOBAUCOUPON del mese è arrivato!"
    subtitle = (
        "Ottieni il tuo sconto o omaggio esclusivo valido fino al 10 dicembre 2025!\n"
        "Mostralo in cassa nel tuo punto vendita MiaoBau preferito e approfittane prima che scada."
    )

    # Load fonts (fallback to default if custom not available)
    try:
        font_bold = ImageFont.truetype("arialbd.ttf", 72)
        font_semibold = ImageFont.truetype("arialbd.ttf", 36)
        font_code = ImageFont.truetype("arialbd.ttf", 84)
        font_small = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font_bold = ImageFont.load_default()
        font_semibold = ImageFont.load_default()
        font_code = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw title on banner
    tw, _ = draw.textlength(title, font=font_bold), 0
    draw.text(((W - tw) / 2, 60), title, font=font_bold, fill=(255, 255, 255))

    # Subtitle
    y = banner_h + 50
    for line in subtitle.split("\n"):
        lw = draw.textlength(line, font=font_semibold)
        draw.text(((W - lw) / 2, y), line, font=font_semibold, fill=TEXT)
        y += 50

    # Coupon card
    card_w, card_h = W - 160, 520
    card_x, card_y = 80, y + 30
    draw.rounded_rectangle([(card_x, card_y), (card_x + card_w, card_y + card_h)], radius=24, fill=(255, 255, 255))
    # Code label
    label = "CODICE COUPON"
    lw = draw.textlength(label, font=font_small)
    draw.text((card_x + (card_w - lw) / 2, card_y + 40), label, font=font_small, fill=TEXT)

    # Code text in red
    cw = draw.textlength(code, font=font_code)
    draw.text((card_x + (card_w - cw) / 2, card_y + 140), code, font=font_code, fill=RED)

    # Instruction
    info = "Mostra questo coupon alla cassa per ottenere lo sconto/omaggio."
    iw = draw.textlength(info, font=font_small)
    draw.text((card_x + (card_w - iw) / 2, card_y + 300), info, font=font_small, fill=TEXT)

    # Footer note
    footer = "Valido fino al 10 dicembre 2025. Uso personale. Promo riservata al canale WhatsApp MiaoBau."
    fw = draw.textlength(footer, font=font_small)
    draw.text(((W - fw) / 2, H - 80), footer, font=font_small, fill=TEXT)

    # Export to bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


@app.post("/coupon")
def generate_coupon():
    """Generate a personalized coupon image (PNG) with a progressive code.
    Code format: WBAU10DIC-XXXXXX
    """
    try:
        seq = _get_next_sequence("coupon")
        code = f"{COUPON_PREFIX}{seq:06d}"

        # Persist document
        doc = Coupon(code=code)
        create_document("coupon", doc)

        # Build image
        png_bytes = _build_coupon_image(code)
        filename = f"miabaucoupon_{code}.png"

        return StreamingResponse(
            io.BytesIO(png_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Coupon-Code": code,
            },
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
