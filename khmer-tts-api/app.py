import os
import uuid
import asyncio
import subprocess
import edge_tts

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

VOICES = {
    "male": "km-KH-PisethNeural",
    "female": "km-KH-SreymomNeural",
}


# =========================================================
# CLEAN TEXT
# =========================================================

def clean_text(text):

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    lines = []

    for line in text.split("\n"):

        line = " ".join(line.split())

        if line:
            lines.append(line)

    return "\n".join(lines).strip()


# =========================================================
# SPLIT STORY INTO SENTENCES
# =========================================================

def split_sentences(text):

    text = clean_text(text)

    if not text:
        return []

    sentences = []
    current = ""

    for char in text:

        current += char

        if char in ["។", "?", "!", "…"]:

            if current.strip():
                sentences.append(current.strip())

            current = ""

    if current.strip():
        sentences.append(current.strip())

    return sentences


# =========================================================
# PAUSE LENGTH
# =========================================================

def get_pause(sentence):

    sentence = sentence.strip()

    if not sentence:
        return 0.4

    if sentence.endswith("?"):
        return 0.75

    if sentence.endswith("!"):
        return 0.70

    if sentence.endswith("…"):
        return 0.90

    if sentence.endswith("។"):
        return 0.65

    return 0.45


# =========================================================
# GENERATE ONE SENTENCE
# =========================================================

async def generate_sentence(
    text,
    voice_name,
    rate,
    pitch,
    volume,
    output_path
):

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice_name,
        rate=rate,
        pitch=pitch,
        volume=volume
    )

    await communicate.save(output_path)


# =========================================================
# CREATE SILENCE MP3 USING FFMPEG
# =========================================================

def create_silence(
    duration,
    output_path
):

    command = [
        "ffmpeg",
        "-y",

        "-f",
        "lavfi",

        "-i",
        "anullsrc=r=24000:cl=mono",

        "-t",
        str(duration),

        "-c:a",
        "libmp3lame",

        "-b:a",
        "128k",

        output_path
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:

        raise Exception(
            "FFmpeg silence error:\n" +
            result.stderr
        )


# =========================================================
# COMBINE MP3 FILES USING FFMPEG
# =========================================================

def combine_audio(
    audio_files,
    pauses,
    output_path
):

    concat_files = []

    temporary_files = []

    try:

        # ---------------------------------------------
        # Create silence files
        # ---------------------------------------------

        for index, audio_file in enumerate(
            audio_files
        ):

            concat_files.append(
                audio_file
            )

            # Don't add unnecessary silence
            # after the final sentence.
            if index < len(audio_files) - 1:

                pause_file = os.path.join(
                    OUTPUT_DIR,
                    f"pause_{uuid.uuid4().hex}.mp3"
                )

                create_silence(
                    pauses[index],
                    pause_file
                )

                concat_files.append(
                    pause_file
                )

                temporary_files.append(
                    pause_file
                )

        # ---------------------------------------------
        # Create concat file
        # ---------------------------------------------

        concat_file = os.path.join(
            OUTPUT_DIR,
            f"concat_{uuid.uuid4().hex}.txt"
        )

        temporary_files.append(
            concat_file
        )

        with open(
            concat_file,
            "w",
            encoding="utf-8"
        ) as f:

            for file_path in concat_files:

                absolute_path = os.path.abspath(
                    file_path
                )

                # FFmpeg concat syntax
                f.write(
                    "file '" +
                    absolute_path.replace(
                        "'",
                        "'\\''"
                    ) +
                    "'\n"
                )

        # ---------------------------------------------
        # Combine
        # ---------------------------------------------

        command = [
            "ffmpeg",
            "-y",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            concat_file,

            "-c:a",
            "libmp3lame",

            "-b:a",
            "192k",

            output_path
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:

            raise Exception(
                "FFmpeg combine error:\n" +
                result.stderr
            )

    finally:

        # ---------------------------------------------
        # Delete temporary silence / concat files
        # ---------------------------------------------

        for file_path in temporary_files:

            try:
                os.remove(file_path)
            except:
                pass


# =========================================================
# GENERATE FULL STORY
# =========================================================

async def generate_story(
    text,
    voice_name,
    rate,
    pitch,
    volume
):

    sentences = split_sentences(text)

    if not sentences:

        raise Exception(
            "No readable text found"
        )

    audio_files = []

    for index, sentence in enumerate(
        sentences
    ):

        filename = (
            f"sentence_{uuid.uuid4().hex}.mp3"
        )

        path = os.path.join(
            OUTPUT_DIR,
            filename
        )

        print(
            f"Generating "
            f"{index + 1}/{len(sentences)}: "
            f"{sentence}"
        )

        await generate_sentence(
            text=sentence,
            voice_name=voice_name,
            rate=rate,
            pitch=pitch,
            volume=volume,
            output_path=path
        )

        audio_files.append(path)

    return (
        audio_files,
        sentences
    )


# =========================================================
# HOME
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "success": True,
        "service": "Khmer Human Story TTS API",
        "status": "online",
        "voices": VOICES
    })


# =========================================================
# VOICES
# =========================================================

@app.route(
    "/api/voices",
    methods=["GET"]
)
def get_voices():

    return jsonify({
        "success": True,
        "voices": VOICES
    })


# =========================================================
# GENERATE MP3
# =========================================================

@app.route(
    "/api/generate",
    methods=["POST"]
)
def generate_mp3():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "error": "No JSON data received"
            }), 400

        text = data.get(
            "text",
            ""
        ).strip()

        if not text:

            return jsonify({
                "success": False,
                "error": "Please provide Khmer text"
            }), 400

        # =================================================
        # VOICE
        # =================================================

        voice = data.get(
            "voice",
            "female"
        )

        if voice in VOICES:

            voice_name = VOICES[voice]

        elif voice in VOICES.values():

            voice_name = voice

        else:

            voice_name = VOICES["female"]

        # =================================================
        # SPEED
        # =================================================

        try:

            speed = float(
                data.get(
                    "rate",
                    0.95
                )
            )

        except:

            speed = 0.95

        speed = max(
            0.75,
            min(1.20, speed)
        )

        rate_percent = int(
            (speed - 1.0) * 100
        )

        if rate_percent >= 0:

            rate = (
                f"+{rate_percent}%"
            )

        else:

            rate = (
                f"{rate_percent}%"
            )

        # =================================================
        # PITCH
        # =================================================

        try:

            pitch_value = float(
                data.get(
                    "pitch",
                    1.0
                )
            )

        except:

            pitch_value = 1.0

        pitch_value = max(
            0.85,
            min(1.15, pitch_value)
        )

        pitch_hz = int(
            (pitch_value - 1.0) * 20
        )

        if pitch_hz >= 0:

            pitch = (
                f"+{pitch_hz}Hz"
            )

        else:

            pitch = (
                f"{pitch_hz}Hz"
            )

        # =================================================
        # VOLUME
        # =================================================

        try:

            volume_value = float(
                data.get(
                    "volume",
                    1.0
                )
            )

        except:

            volume_value = 1.0

        volume_value = max(
            0.70,
            min(1.20, volume_value)
        )

        volume_percent = int(
            (volume_value - 1.0) * 100
        )

        if volume_percent >= 0:

            volume = (
                f"+{volume_percent}%"
            )

        else:

            volume = (
                f"{volume_percent}%"
            )

        # =================================================
        # GENERATE SENTENCES
        # =================================================

        audio_files, sentences = asyncio.run(
            generate_story(
                text=text,
                voice_name=voice_name,
                rate=rate,
                pitch=pitch,
                volume=volume
            )
        )

        # =================================================
        # PAUSES
        # =================================================

        pauses = [
            get_pause(sentence)
            for sentence in sentences
        ]

        # =================================================
        # FINAL FILE
        # =================================================

        final_filename = (
            f"{uuid.uuid4().hex}.mp3"
        )

        final_path = os.path.join(
            OUTPUT_DIR,
            final_filename
        )

        # =================================================
        # COMBINE
        # =================================================

        combine_audio(
            audio_files=audio_files,
            pauses=pauses,
            output_path=final_path
        )

        # =================================================
        # DELETE SENTENCE FILES
        # =================================================

        for file_path in audio_files:

            try:
                os.remove(file_path)
            except:
                pass

        # =================================================
        # URL
        # =================================================

        base_url = (
            request.host_url.rstrip("/")
        )

        audio_url = (
            f"{base_url}/api/audio/"
            f"{final_filename}"
        )

        download_url = (
            f"{base_url}/api/download/"
            f"{final_filename}"
        )

        # =================================================
        # RESPONSE
        # =================================================

        return jsonify({

            "success": True,

            "message":
                "Natural Khmer MP3 generated successfully",

            "filename":
                final_filename,

            "voice":
                voice_name,

            "rate":
                rate,

            "pitch":
                pitch,

            "volume":
                volume,

            "sentences":
                len(sentences),

            "audio_url":
                audio_url,

            "download_url":
                download_url
        })

    except Exception as e:

        print(
            "TTS ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# =========================================================
# AUDIO
# =========================================================

@app.route(
    "/api/audio/<filename>",
    methods=["GET"]
)
def audio(filename):

    return send_from_directory(
        OUTPUT_DIR,
        filename,
        mimetype="audio/mpeg"
    )


# =========================================================
# DOWNLOAD
# =========================================================

@app.route(
    "/api/download/<filename>",
    methods=["GET"]
)
def download(filename):

    return send_from_directory(
        OUTPUT_DIR,
        filename,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name=filename
    )


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
