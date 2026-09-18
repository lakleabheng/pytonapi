import os
import uuid
import asyncio
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
# TEXT CLEANING
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
# SPLIT KHMER STORY INTO SENTENCES
# =========================================================

def split_sentences(text):
    """
    Split Khmer story into natural speaking chunks.
    """

    text = clean_text(text)

    if not text:
        return []

    sentences = []

    current = ""

    for char in text:

        current += char

        # Khmer sentence ending
        if char in ["។", "?", "!", "…"]:

            if current.strip():
                sentences.append(current.strip())

            current = ""

        # New paragraph
        elif char == "\n":

            if current.strip():
                sentences.append(current.strip())

            current = ""

    if current.strip():
        sentences.append(current.strip())

    return sentences


# =========================================================
# DETERMINE PAUSE AFTER SENTENCE
# =========================================================

def get_pause(sentence):

    sentence = sentence.strip()

    if not sentence:
        return 0.4

    # Question
    if sentence.endswith("?"):
        return 0.75

    # Excitement
    if sentence.endswith("!"):
        return 0.70

    # Khmer full stop
    if sentence.endswith("។"):
        return 0.65

    # Ellipsis
    if sentence.endswith("…"):
        return 0.90

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
# GENERATE FULL STORY
# =========================================================

async def generate_story(
    text,
    voice_name,
    rate,
    pitch,
    volume,
    output_dir
):

    sentences = split_sentences(text)

    if not sentences:
        raise Exception("No readable text found")

    files = []

    for index, sentence in enumerate(sentences):

        filename = f"part_{uuid.uuid4().hex}.mp3"

        path = os.path.join(
            output_dir,
            filename
        )

        print(
            f"Generating sentence "
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

        files.append(path)

    return files


# =========================================================
# COMBINE AUDIO
# =========================================================

def combine_audio(files, output_path, pauses):
    """
    Combine MP3 files using pydub.
    """

    from pydub import AudioSegment

    final_audio = AudioSegment.empty()

    for index, file_path in enumerate(files):

        audio = AudioSegment.from_mp3(file_path)

        final_audio += audio

        if index < len(files):

            pause_seconds = pauses[index]

            silence = AudioSegment.silent(
                duration=int(pause_seconds * 1000)
            )

            final_audio += silence

    final_audio.export(
        output_path,
        format="mp3",
        bitrate="192k"
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

@app.route("/api/voices", methods=["GET"])
def get_voices():

    return jsonify({
        "success": True,
        "voices": VOICES
    })


# =========================================================
# GENERATE MP3
# =========================================================

@app.route("/api/generate", methods=["POST"])
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
        # RATE
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

        # Storytelling speed
        speed = max(
            0.75,
            min(1.20, speed)
        )

        rate_percent = int(
            (speed - 1.0) * 100
        )

        if rate_percent >= 0:

            rate = f"+{rate_percent}%"

        else:

            rate = f"{rate_percent}%"

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

            pitch = f"+{pitch_hz}Hz"

        else:

            pitch = f"{pitch_hz}Hz"

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

            volume = f"+{volume_percent}%"

        else:

            volume = f"{volume_percent}%"

        # =================================================
        # FILE NAMES
        # =================================================

        story_id = uuid.uuid4().hex

        final_filename = (
            f"{story_id}.mp3"
        )

        final_path = os.path.join(
            OUTPUT_DIR,
            final_filename
        )

        # =================================================
        # GENERATE SENTENCES
        # =================================================

        sentence_files = asyncio.run(
            generate_story(
                text=text,
                voice_name=voice_name,
                rate=rate,
                pitch=pitch,
                volume=volume,
                output_dir=OUTPUT_DIR
            )
        )

        # =================================================
        # PAUSES
        # =================================================

        sentences = split_sentences(text)

        pauses = []

        for sentence in sentences:

            pauses.append(
                get_pause(sentence)
            )

        # =================================================
        # COMBINE
        # =================================================

        combine_audio(
            files=sentence_files,
            output_path=final_path,
            pauses=pauses
        )

        # =================================================
        # DELETE TEMP FILES
        # =================================================

        for file_path in sentence_files:

            try:

                os.remove(file_path)

            except:

                pass

        # =================================================
        # URL
        # =================================================

        base_url = (
            request.host_url
            .rstrip("/")
        )

        audio_url = (
            f"{base_url}/api/audio/"
            f"{final_filename}"
        )

        download_url = (
            f"{base_url}/api/download/"
            f"{final_filename}"
        )

        return jsonify({

            "success": True,

            "message":
                "Natural Khmer story MP3 generated successfully",

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
# PLAY AUDIO
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
# RUN
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
