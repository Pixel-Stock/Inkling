"""
generate_handler.py
AWS Lambda handler for Inkling — AI poem & story generator.

Runtime:  Python 3.12
Trigger:  Lambda function URL (Auth: NONE, CORS: enabled)
Memory:   256 MB  |  Timeout: 15 s

Calls Amazon Bedrock's Converse API with amazon.nova-2-lite-v1:0
to generate original, family-friendly poems and short stories.
"""

import json
import os
import re
import time
import uuid
import logging
from botocore.exceptions import ClientError

import boto3

# ── Logging ──────────────────────────────────────────────────
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Configuration (overridable via Lambda env vars) ──────────
REGION     = os.environ.get("BEDROCK_REGION", "us-east-1")
MODEL_ID   = os.environ.get("MODEL_ID", "amazon.nova-2-lite-v1:0")
TABLE_NAME = os.environ.get("TABLE_NAME")          # unset until P1 gallery is built

# ── AWS Clients (initialised outside handler for reuse) ──────
bedrock  = boto3.client("bedrock-runtime", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION) if TABLE_NAME else None
table    = dynamodb.Table(TABLE_NAME) if dynamodb else None

# ── Valid Moods ───────────────────────────────────────────────
VALID_MOODS = {
    "whimsical", "adventurous", "cozy",
    "mysterious", "funny", "romantic", "bittersweet",
}

# ── CORS headers (returned on every response, including errors) ──
# Scope to your CloudFront/Amplify domain in production; '*' for local testing.
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

CORS_HEADERS = {
    "Content-Type":                 "application/json",
    "Access-Control-Allow-Origin":  CORS_ORIGIN,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# ── Input helpers ─────────────────────────────────────────────

def sanitize(text: str | None, max_len: int) -> str:
    """Strip non-printable/special chars and truncate to max_len."""
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s.,!?'\"()&\-]", "", str(text)).strip()
    return cleaned[:max_len]


def parse_body(event: dict) -> dict:
    """Extract and JSON-decode the request body from a Lambda function URL event."""
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


# ── Prompt builder ────────────────────────────────────────────

def build_prompt(name: str, theme: str, mood: str, fmt: str, length: str) -> tuple[str, str]:
    word_budget = "80–150 words" if length == "short" else "180–280 words"

    system_prompt = (
        "You are Inkling, a warm and playful creative-writing companion. "
        f"You write short, original {fmt}s that are family-friendly, positive, "
        "and a little bit magical. Never include violence, hate, or adult content. "
        f"Stay within {word_budget}. "
        "Always respond with ONLY a short, charming title on the very first line, "
        "then a blank line, then the piece itself — nothing else, "
        "no explanations, no labels, no quotation marks around the title."
    )

    name_phrase  = f"starring or dedicated to '{name}'" if name else "with an unnamed protagonist"
    theme_phrase = f"inspired by this theme: '{theme}'" if theme else "on the theme of everyday wonder"

    user_prompt = (
        f"Write a {mood} {fmt} {name_phrase}, {theme_phrase}."
    )

    return system_prompt, user_prompt


# ── DynamoDB save (P1) ────────────────────────────────────────

def save_creation(item: dict, name: str, theme: str, mood: str) -> None:
    """Persist a generation to DynamoDB for the gallery view (P1)."""
    if not table:
        return
    sk = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}#{item['id']}"
    try:
        table.put_item(Item={
            "PK":         "GALLERY",
            "SK":         sk,
            "creationId": item["id"],
            "title":      item["title"],
            "outputText": item["text"],
            "format":     item["format"],
            "mood":       mood,
            "name":       name or "a curious traveler",
            "theme":      theme or "a rainy afternoon",
            "createdAt":  item["createdAt"],
        })
        logger.info("Saved creation %s to DynamoDB", item["id"])
    except ClientError as exc:
        # Log but don't fail the request if DynamoDB write fails
        logger.warning("DynamoDB save failed: %s", exc)


# ── Response helper ───────────────────────────────────────────

def _response(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers":    CORS_HEADERS,
        "body":       json.dumps(payload),
    }


# ── Handler ───────────────────────────────────────────────────

def handler(event: dict, context) -> dict:  # noqa: ANN001
    logger.info("Event method: %s", event.get("requestContext", {}).get("http", {}).get("method"))

    # ── Handle CORS pre-flight ────────────────────────────────
    method = (
        event.get("requestContext", {})
             .get("http", {})
             .get("method", "")
             .upper()
    )
    if method == "OPTIONS":
        return _response(200, {"message": "OK"})

    # ── Parse body ────────────────────────────────────────────
    try:
        body = parse_body(event)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Bad request body: %s", exc)
        return _response(400, {"error": "Malformed request body — please send valid JSON."})

    # ── Validate & sanitize inputs ────────────────────────────
    name   = sanitize(body.get("name"), 60)   or "a curious traveler"
    theme  = sanitize(body.get("theme"), 100) or "a rainy afternoon"
    mood   = body.get("mood") if body.get("mood") in VALID_MOODS else "whimsical"
    fmt    = "story" if body.get("format") == "story" else "poem"
    length = "medium" if body.get("length") == "medium" else "short"

    logger.info("Generating %s | mood=%s | length=%s | name=%r | theme=%r",
                fmt, mood, length, name[:20], theme[:40])

    # ── Build prompt ──────────────────────────────────────────
    system_prompt, user_prompt = build_prompt(name, theme, mood, fmt, length)

    # ── Call Bedrock (with one retry on throttle) ─────────────
    raw_text = None
    for attempt in range(2):
        try:
            result = bedrock.converse(
                modelId=MODEL_ID,
                system=[{"text": system_prompt}],
                messages=[{
                    "role":    "user",
                    "content": [{"text": user_prompt}],
                }],
                inferenceConfig={
                    "maxTokens":   500,
                    "temperature": 0.95,
                    "topP":        0.9,
                },
            )
            raw_text = result["output"]["message"]["content"][0]["text"].strip()
            break  # success — exit retry loop

        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "ThrottlingException" and attempt == 0:
                logger.warning("Bedrock throttled; retrying after 1 s …")
                time.sleep(1)
                continue
            logger.error("Bedrock ClientError: %s", exc)
            return _response(502, {
                "error": "Inkling got a little tongue-tied — try again?"
            })
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected Bedrock error: %s", exc)
            return _response(502, {
                "error": "Inkling got a little tongue-tied — try again?"
            })

    if raw_text is None:
        return _response(502, {"error": "Inkling got a little tongue-tied — try again?"})

    # ── Parse title / body ────────────────────────────────────
    # Expected format: "<Title>\n\n<piece text>"
    title, sep, piece = raw_text.partition("\n\n")
    if not sep or not piece.strip():
        # Fallback: treat the whole thing as the body
        title = "Untitled"
        piece = raw_text

    title = title.strip()
    piece = piece.strip()

    # ── Build response item ───────────────────────────────────
    item = {
        "id":        str(uuid.uuid4()),
        "title":     title,
        "text":      piece,
        "format":    fmt,
        "createdAt": int(time.time()),
    }

    # ── P1: save to DynamoDB (uncomment after table is created) ──
    if TABLE_NAME:
        save_creation(item, name, theme, mood)

    logger.info("Generated '%s' (%d chars)", title, len(piece))
    return _response(200, item)
