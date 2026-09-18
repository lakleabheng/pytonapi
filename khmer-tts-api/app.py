import os
import uuid
import asyncio
import edge_tts

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =========================
# CONFIG
# =========================

OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Khmer voices
VOICES = {
    "male": "km-KH-PisethNeural",
    "female": "km-KH-SreymomNeural",
}


# =========================
# HOME
# =========================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "service": "Khmer TTS API",
        "status": "online",
        "voices": VOICES
    })


# =========================
# GET VOICES
# =========================

@app.route("/api/voices", methods=["GET"])
def get_voices():
    return jsonify({
        "success": True,
        "voices": VOICES
    })


# =========================
# GENERATE MP3
# =========================

@app.route("/api/generate", methods=["POST"])
def generate_mp3():

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data received"
            }), 400

        # -------------------------
        # TEXT
        # -------------------------

        text = data.get("text", "").strip()

        if not text:
            return jsonify({
                "success": False,
                "error": "Please provide Khmer text"
            }), 400

        # -------------------------
        # VOICE
        # -------------------------

        voice = data.get("voice", "female")

        if voice in VOICES:
            voice_name = VOICES[voice]
        elif voice in VOICES.values():
            voice_name = voice
        else:
            voice_name = VOICES["female"]

        # -------------------------
        # SPEED
        # -------------------------

        speed = data.get("speed", 1.0)

        try:
            speed = float(speed)
        except:
            speed = 1.0

        # Edge TTS rate
        rate_percent = int((speed - 1.0) * 100)

        if rate_percent >= 0:
            rate = f"+{rate_percent}%"
        else:
            rate = f"{rate_percent}%"

        # -------------------------
        # PITCH
        # -------------------------

        pitch_value = data.get("pitch", 1.0)

        try:
            pitch_value = float(pitch_value)
        except:
            pitch_value = 1.0

        # Convert 1.0 = 0Hz
        pitch_hz = int((pitch_value - 1.0) * 20)

        if pitch_hz >= 0:
            pitch = f"+{pitch_hz}Hz"
        else:
            pitch = f"{pitch_hz}Hz"

        # -------------------------
        # VOLUME
        # -------------------------

        volume_value = data.get("volume", 1.0)

        try:
            volume_value = float(volume_value)
        except:
            volume_value = 1.0

        volume_percent = int((volume_value - 1.0) * 100)

        if volume_percent >= 0:
            volume = f"+{volume_percent}%"
        else:
            volume = f"{volume_percent}%"

        # -------------------------
        # FILE NAME
        # -------------------------

        filename = f"{uuid.uuid4().hex}.mp3"

        output_path = os.path.join(
            OUTPUT_DIR,
            filename
        )

        # -------------------------
        # GENERATE AUDIO
        # -------------------------

        async def create_audio():

            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_name,
                rate=rate,
                pitch=pitch,
                volume=volume
            )

            await communicate.save(output_path)

        asyncio.run(create_audio())

        # -------------------------
        # URL
        # -------------------------

        base_url = request.host_url.rstrip("/")

        audio_url = f"{base_url}/api/audio/{filename}"
        download_url = f"{base_url}/api/download/{filename}"

        return jsonify({
            "success": True,
            "message": "MP3 generated successfully",
            "filename": filename,
            "voice": voice_name,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "audio_url": audio_url,
            "download_url": download_url
        })

    except Exception as e:

        print("TTS ERROR:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================
# PLAY AUDIO
# =========================

@app.route("/api/audio/<filename>", methods=["GET"])
def audio(filename):

    return send_from_directory(
        OUTPUT_DIR,
        filename,
        mimetype="audio/mpeg"
    )


# =========================
# DOWNLOAD AUDIO
# =========================

@app.route("/api/download/<filename>", methods=["GET"])
def download(filename):

    return send_from_directory(
        OUTPUT_DIR,
        filename,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name=filename
    )


# =========================
# RUN SERVER
# =========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )