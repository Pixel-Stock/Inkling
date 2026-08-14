"""
local_server.py  - Inkling local dev server
Serves the frontend on / and the API on /generate
Run: python local_server.py
"""

import json
import os
import re
import uuid
import time
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# ── Try different model / region combos until one works ──────
CANDIDATES = [
    ("us-east-1",  "us.amazon.nova-lite-v1:0"),
    ("us-east-1",  "amazon.nova-lite-v1:0"),
    ("ap-south-1", "ap.amazon.nova-lite-v1:0"),
    ("ap-south-1", "amazon.nova-lite-v1:0"),
]

FRONTEND_DIR = "frontend"

VALID_MOODS = {
    "whimsical", "adventurous", "cozy",
    "mysterious", "funny", "romantic", "bittersweet",
}


def check_credentials():
    """Verify AWS credentials exist before starting. Exit with clear instructions if not."""
    try:
        sts = boto3.client("sts", region_name="us-east-1")
        identity = sts.get_caller_identity()
        print(f"[OK] AWS credentials found. Account: {identity['Account']}")
        return True
    except NoCredentialsError:
        print()
        print("=" * 60)
        print("ERROR: No AWS credentials found on this machine!")
        print("=" * 60)
        print()
        print("To fix this, run these commands in PowerShell BEFORE")
        print("starting this server:")
        print()
        print('  $env:AWS_ACCESS_KEY_ID     = "PASTE_YOUR_KEY_ID_HERE"')
        print('  $env:AWS_SECRET_ACCESS_KEY = "PASTE_YOUR_SECRET_HERE"')
        print('  $env:AWS_DEFAULT_REGION    = "us-east-1"')
        print('  python local_server.py')
        print()
        print("To create an access key:")
        print("  1. Go to https://console.aws.amazon.com/iam/")
        print("  2. Click Users -> your username -> Security credentials")
        print("  3. Click 'Create access key' -> choose CLI")
        print("  4. Copy both Key ID and Secret Key")
        print()
        return False
    except Exception as e:
        print(f"[WARN] Could not verify credentials: {e}")
        print("       Continuing anyway - will fail at first Bedrock call if creds are bad.")
        return True


def sanitize(text, max_len):
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s.,!?'\"()&\-]", "", str(text)).strip()
    return cleaned[:max_len]


def build_prompt(name, theme, mood, fmt, length):
    if fmt == "poem":
        structure   = "a short poem of 2 stanzas" if length == "short" else "a poem of exactly 4 stanzas"
        word_budget = "60-100 words" if length == "short" else "150-250 words"
    else:
        structure   = "a short story of 2-3 paragraphs" if length == "short" else "a detailed story of 6-8 paragraphs"
        word_budget = "150-200 words" if length == "short" else "400-600 words"

    system_prompt = (
        f"You are Inkling, a brilliant creative author. Write beautifully crafted {fmt}s. "
        f"Structure: {structure}. Word budget: {word_budget}. "
        "Respond ONLY with a concise, evocative title of 2-5 words on line 1, "
        "a blank line, then the COMPLETE piece. Never cut it short abruptly; always write the full piece and end it gracefully with a concluding sentence. No labels or quotes."
    )
    name_phrase  = f"starring '{name}'" if name else "with an unnamed protagonist"
    theme_phrase = f"inspired by '{theme}'" if theme else "on the theme of everyday wonder"
    user_prompt  = f"Write a {mood} {fmt} {name_phrase}, {theme_phrase}."
    return system_prompt, user_prompt


def call_bedrock(body):
    name   = sanitize(body.get("name"),  60) or "a curious traveler"
    theme  = sanitize(body.get("theme"), 100) or "a rainy afternoon"
    mood   = body.get("mood") if body.get("mood") in VALID_MOODS else "whimsical"
    fmt    = "story" if body.get("format") == "story" else "poem"
    length = "long"  if body.get("length") == "long"  else "short"

    system_prompt, user_prompt = build_prompt(name, theme, mood, fmt, length)
    max_tokens = 5120 if length == "long" else 2000

    last_error = None
    for region, model_id in CANDIDATES:
        try:
            print(f"  Trying region={region}  model={model_id}")
            bedrock = boto3.client("bedrock-runtime", region_name=region)
            result  = bedrock.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0.7, "topP": 0.9},
            )
            raw = result["output"]["message"]["content"][0]["text"].strip()
            title, sep, piece = raw.partition("\n\n")
            if not sep or not piece.strip():
                title, piece = "Untitled", raw
            print(f"  SUCCESS: region={region}  model={model_id}")
            return {
                "id":        str(uuid.uuid4()),
                "title":     title.strip(),
                "text":      piece.strip(),
                "format":    fmt,
                "createdAt": int(time.time()),
            }, None
        except NoCredentialsError:
            print("  FAIL: No AWS credentials. Set env vars and restart.")
            return None, "Unable to locate credentials — set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg  = e.response["Error"]["Message"]
            print(f"  FAIL [{code}]: {msg}")
            last_error = f"{code}: {msg}"
        except Exception as e:
            print(f"  FAIL [{type(e).__name__}]: {e}")
            last_error = str(e)

    return None, last_error


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == "/generate":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            try:
                body = json.loads(raw)
            except Exception:
                body = {}

            print(f"\nPOST /generate  payload={body}")
            item, err = call_bedrock(body)
            if item:
                self._json(200, item)
            else:
                self._json(502, {"error": f"Bedrock error: {err}"})
        else:
            self.send_error(404, "Not found")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # silence access logs


if __name__ == "__main__":
    print()
    print("Inkling Local Dev Server")
    print("-" * 40)
    if not check_credentials():
        sys.exit(1)
    print(f"Starting on http://localhost:3000")
    print(f"Bedrock candidates: {[m for _, m in CANDIDATES]}")
    print()
    server = HTTPServer(("", 3000), Handler)
    server.serve_forever()
