from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import edge_tts
import asyncio
import os
import uuid

app = Flask(__name__)
CORS(app)

OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)


VOICES = {
    "km-KH-PisethNeural": "Piseth - Male",
    "km-KH-SreymomNeural": "Sreymom - Female"
}


def convert_rate(value):
    value = float(value)

    percent = round((value - 1) * 100)

    if percent >= 0:
        return f"+{percent}%"

    return f"{percent}%"


def convert_pitch(value):
    value = float(value)

    hz = round((value - 1) * 100)

    if hz >= 0:
        return f"+{hz}Hz"

    return f"{hz}Hz"


def convert_volume(value):
    value = float(value)

    percent = round((value - 1) * 100)

    if percent >= 0:
        return f"+{percent}%"

    return f"{percent}%"


async def generate_audio(
    text,
    voice,
    rate,
    pitch,
    volume,
    filename
):

    tts = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume
    )

    await tts.save(filename)


@app.route("/")
def home():

    return jsonify({
        "success": True,
        "service": "Khmer TTS API",
        "voices": list(VOICES.keys())
    })


@app.route("/api/voices")
def get_voices():

    return jsonify([
        {
            "id": voice,
            "name": name
        }
        for voice, name in VOICES.items()
    ])


@app.route("/api/generate", methods=["POST"])
def generate():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is empty"
            }), 400


        text = str(
            data.get("text", "")
        ).strip()


        if not text:

            return jsonify({
                "success": False,
                "error": "Text is empty"
            }), 400


        voice = data.get(
            "voice",
            "km-KH-PisethNeural"
        )


        if voice not in VOICES:

            voice = "km-KH-PisethNeural"


        rate = convert_rate(
            data.get("rate", 1.05)
        )

        pitch = convert_pitch(
            data.get("pitch", 1.0)
        )

        volume = convert_volume(
            data.get("volume", 1.0)
        )


        filename = (
            "khmer_" +
            uuid.uuid4().hex +
            ".mp3"
        )


        filepath = os.path.join(
            OUTPUT_DIR,
            filename
        )


        asyncio.run(
            generate_audio(
                text,
                voice,
                rate,
                pitch,
                volume,
                filepath
            )
        )


        return jsonify({

            "success": True,

            "filename": filename,

            "audio_url":
                "/api/audio/" + filename,

            "download_url":
                "/api/download/" + filename

        })


    except Exception as e:

        print("ERROR:", str(e))

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


@app.route("/api/audio/<filename>")
def play_audio(filename):

    filepath = os.path.join(
        OUTPUT_DIR,
        filename
    )


    if not os.path.exists(filepath):

        return jsonify({
            "error": "Audio file not found"
        }), 404


    return send_file(
        filepath,
        mimetype="audio/mpeg"
    )


@app.route("/api/download/<filename>")
def download_audio(filename):

    filepath = os.path.join(
        OUTPUT_DIR,
        filename
    )


    if not os.path.exists(filepath):

        return jsonify({
            "error": "Audio file not found"
        }), 404


    return send_file(
        filepath,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name=filename
    )


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
