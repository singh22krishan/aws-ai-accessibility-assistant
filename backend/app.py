"""Serverless image-to-audio accessibility API built with AWS Chalice.

The API temporarily stores an uploaded image in S3, uses Rekognition for labels
and OCR, optionally translates the generated description, converts the text to
speech with Polly, and returns a short-lived pre-signed URL to the MP3.
"""

import logging
import os
import uuid
from typing import Optional

import boto3
from chalice import Chalice, CORSConfig, Response

app = Chalice(app_name="image-accessibility-assistant")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")
translate = boto3.client("translate")
polly = boto3.client("polly")

BUCKET = os.environ.get("S3_BUCKET", "")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://127.0.0.1:8000")
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", str(5 * 1024 * 1024)))
AUDIO_URL_TTL_SECONDS = int(os.environ.get("AUDIO_URL_TTL_SECONDS", "300"))

cors = CORSConfig(
    allow_origin=ALLOWED_ORIGIN,
    allow_headers=["Content-Type"],
    max_age=600,
)

SUPPORTED_LANGUAGES = {
    "en": ("Joanna", "en-US"),
    "es": ("Lupe", "es-US"),
    "fr": ("Celine", "fr-FR"),
    "de": ("Marlene", "de-DE"),
    "hi": ("Aditi", "hi-IN"),
}


def response(message: dict, status_code: int) -> Response:
    return Response(body=message, status_code=status_code)


def detect_image_format(data: bytes) -> Optional[str]:
    """Allow only JPEG and PNG based on file signatures, not file names."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def parse_multipart(raw_body: bytes, content_type: str):
    if "boundary=" not in content_type:
        return None, "en"

    boundary = content_type.split("boundary=", 1)[1].strip().strip('"')
    image_data = None
    language_code = "en"

    for part in raw_body.split(("--" + boundary).encode()):
        if b"Content-Disposition:" not in part:
            continue
        if b'name="image"' in part:
            payload = part.split(b"\r\n\r\n", 1)
            if len(payload) == 2:
                image_data = payload[1].rstrip(b"\r\n-")
        elif b'name="language"' in part:
            payload = part.split(b"\r\n\r\n", 1)
            if len(payload) == 2:
                language_code = payload[1].decode("utf-8", errors="ignore").strip("\r\n-")

    return image_data, language_code


@app.route("/health", methods=["GET"], cors=cors)
def health():
    return {"status": "ok"}


@app.route("/upload", methods=["POST"], cors=cors, content_types=["multipart/form-data"])
def upload():
    if not BUCKET:
        logger.error("S3_BUCKET is not configured")
        return response({"error": "Service configuration error."}, 500)

    request = app.current_request
    content_type = request.headers.get("content-type", "")
    image_data, language_code = parse_multipart(request.raw_body, content_type)

    if not image_data:
        return response({"error": "No image found."}, 400)
    if len(image_data) > MAX_IMAGE_BYTES:
        return response({"error": "Image is larger than the configured upload limit."}, 413)

    image_content_type = detect_image_format(image_data)
    if not image_content_type:
        return response({"error": "Only JPEG and PNG images are supported."}, 415)
    if language_code not in SUPPORTED_LANGUAGES:
        return response({"error": "Unsupported language."}, 400)

    extension = ".png" if image_content_type == "image/png" else ".jpg"
    image_key = f"images/{uuid.uuid4()}{extension}"

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=image_key,
            Body=image_data,
            ContentType=image_content_type,
            ServerSideEncryption="AES256",
            Tagging="temporary=true",
        )

        labels_result = rekognition.detect_labels(
            Image={"S3Object": {"Bucket": BUCKET, "Name": image_key}},
            MaxLabels=10,
        )
        labels = [label["Name"] for label in labels_result.get("Labels", [])]

        text_result = rekognition.detect_text(
            Image={"S3Object": {"Bucket": BUCKET, "Name": image_key}}
        )
        text_lines = [
            item["DetectedText"]
            for item in text_result.get("TextDetections", [])
            if item.get("Type") == "LINE"
        ]

        description = "This image may contain: " + (", ".join(labels) or "unidentified content")
        if text_lines:
            description += ". It also contains text: " + "; ".join(text_lines)
        description += "."

        logger.info(
            "Image processed successfully: labels=%d, text_lines=%d",
            len(labels),
            len(text_lines),
        )

        voice_id, polly_language = SUPPORTED_LANGUAGES[language_code]
        if language_code == "en":
            spoken_text = description
        else:
            translated = translate.translate_text(
                Text=description,
                SourceLanguageCode="en",
                TargetLanguageCode=language_code,
            )
            spoken_text = translated["TranslatedText"]

        speech = polly.synthesize_speech(
            Text=spoken_text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            LanguageCode=polly_language,
        )

        audio_key = f"audio/{uuid.uuid4()}.mp3"
        s3.upload_fileobj(
            speech["AudioStream"],
            BUCKET,
            audio_key,
            ExtraArgs={
                "ContentType": "audio/mpeg",
                "ServerSideEncryption": "AES256",
                "Tagging": "auto-delete=true",
            },
        )

        audio_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": BUCKET, "Key": audio_key},
            ExpiresIn=AUDIO_URL_TTL_SECONDS,
        )
        return {"audioUrl": audio_url, "description": description}

    except Exception:
        logger.exception("Image processing failed")
        return response({"error": "Image processing failed."}, 500)
    finally:
        try:
            s3.delete_object(Bucket=BUCKET, Key=image_key)
        except Exception:
            logger.warning("Temporary image cleanup failed", exc_info=True)
