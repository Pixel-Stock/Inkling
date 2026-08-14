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
MODEL_ID   = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")
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

# CORS is handled entirely by Lambda Function URL settings.
# Do NOT add Access-Control-Allow-Origin here — it would duplicate the header.
RESPONSE_HEADERS = {
    "Content-Type": "application/json",
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

def build_prompt(name: str, theme: str, mood: str, fmt: str, length: str, tone: str, style: str, perspective: str) -> tuple[str, str]:
    if fmt == "poem":
        if length == "short":
            structure = "a short poem consisting of exactly 2 stanzas"
            word_budget = "around 60-100 words"
        else:
            structure = "a longer, immersive poem consisting of exactly 4 stanzas"
            word_budget = "around 150-250 words"
    else:
        if length == "short":
            structure = "a short story consisting of exactly 2-3 paragraphs"
            word_budget = "around 150-200 words"
        else:
            structure = "a detailed, long story consisting of exactly 6-8 full paragraphs"
            word_budget = "around 400-600 words"

    system_prompt = (
        "You are Inkling, a brilliant, highly acclaimed, and deeply creative author. "
        f"You write beautifully crafted {fmt}s that are family-friendly, positive, and evocative. "
        f"The requested structure is: {structure}. You must adhere strictly to this length. "
        f"Your word budget is {word_budget}. "
        "Use vivid, striking imagery, rich vocabulary, and emotional depth to truly wow the reader. "
        "Always respond with ONLY a concise, evocative title of 2-5 words on the very first line, "
        "then a blank line, then the COMPLETE piece itself — never cut it short, always write the full piece. "
        "Do not use quotation marks around the title."
    )

    name_phrase = f"starring or dedicated to '{name}'" if name else "with an unnamed protagonist"
    theme_phrase = f"inspired by the theme: '{theme}'" if theme else "on the theme of everyday wonder"
    
    tone_str = f" in a {tone} tone" if tone else ""
    style_str = f" in a {style} style" if style else ""
    
    persp_map = {"first": "first person (I/we)", "second": "second person (you)", "third": "third person (he/she/they)"}
    persp_str = f" from a {persp_map.get(perspective, 'third person')} perspective" if perspective else ""

    user_prompt = (
        f"Write a {mood} {fmt}{tone_str}{style_str}{persp_str}, {name_phrase}, {theme_phrase}."
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
        "headers":    RESPONSE_HEADERS,
        "body":       json.dumps(payload),
    }


# ── Handler ───────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:  # noqa: ANN001
    logger.info("Event method: %s", event.get("requestContext", {}).get("http", {}).get("method"))

    # ── Handle CORS pre-flight ────────────────────────────────
    # Lambda Function URL handles OPTIONS/CORS automatically.
    # We only need to handle POST.
    method = (
        event.get("requestContext", {})
             .get("http", {})
             .get("method", "")
             .upper()
    )
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": RESPONSE_HEADERS, "body": ""}

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
    length = "long" if body.get("length") == "long" else "short"
    tone   = body.get("tone", "")
    style  = body.get("style", "")
    persp  = body.get("perspective", "")

    logger.info("Generating %s | mood=%s | length=%s | name=%r | theme=%r",
                fmt, mood, length, name[:20], theme[:40])

    # ── Build prompt ──────────────────────────────────────────
    system_prompt, user_prompt = build_prompt(name, theme, mood, fmt, length, tone, style, persp)

    # ── Call Bedrock ─────────────────────────────
    CANDIDATES = [
        ("us-east-1",  "us.amazon.nova-lite-v1:0"),
        ("us-east-1",  "amazon.nova-lite-v1:0"),
        ("ap-south-1", "ap.amazon.nova-lite-v1:0"),
        ("ap-south-1", "amazon.nova-lite-v1:0"),
    ]

    raw_text = None
    last_err = None
    
    for region, model_id in CANDIDATES:
        try:
            logger.info("Trying region=%s model=%s", region, model_id)
            client = boto3.client("bedrock-runtime", region_name=region)
            result = client.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=[{
                    "role":    "user",
                    "content": [{"text": user_prompt}],
                }],
                inferenceConfig={
                    "maxTokens":   2000 if length == "long" else 600,
                    "temperature": 0.95,
                    "topP":        0.9,
                },
            )
            raw_text = result["output"]["message"]["content"][0]["text"].strip()
            logger.info("SUCCESS with region=%s model=%s", region, model_id)
            break  # success — exit retry loop
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            msg = exc.response["Error"]["Message"]
            logger.warning("Bedrock ClientError (%s): %s", code, msg)
            last_err = f"Bedrock Error ({code}): {msg}"
            if code == "ThrottlingException":
                time.sleep(1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unexpected Bedrock error: %s", exc)
            last_err = f"Unexpected Lambda Error: {str(exc)}"

    if raw_text is None:
        return _response(502, {"error": last_err or "Inkling got a little tongue-tied — try again?"})

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
