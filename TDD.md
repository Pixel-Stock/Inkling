# Technical Design Document (TDD)
## Inkling — AWS architecture & implementation spec

**Companion docs:** `PRD.md` (product requirements), `HANDOFF_PROMPT.md` (paste-ready kickoff prompt)
**How to use this doc if you're the one coding it:** build in priority order — everything tagged P0 first (that's the whole pass/fail bar), then P1, then P2 only if time is left. Every design choice here optimizes for "fastest honest path to a working AWS deployment," not for production robustness.

---

## 1. Architecture overview

A visual of this exact architecture was shown alongside this document in chat. In words:

A visitor's browser loads a static frontend from **S3 + CloudFront** (or Amplify Hosting). When they click Generate, the browser calls a **Lambda function URL**, which invokes **Amazon Bedrock's Nova 2 Lite model** to write the piece, and — optionally, P1 — writes a copy to **DynamoDB** for a gallery view. CloudWatch Logs captures Lambda's logs automatically; no extra wiring needed.

```
Browser
  ├── GET /  ─────────────────► S3 + CloudFront (static HTML/CSS/JS)
  └── POST /generate ─────────► Lambda function URL
                                    │
                                    ├──► Bedrock Converse API (amazon.nova-2-lite-v1:0)
                                    └──► DynamoDB (optional, P1: save creation)
```

## 2. AWS services used

| Service | Role | Free tier tier |
|---------|------|-----------------|
| **Amazon Bedrock** (Nova 2 Lite) | Generates the story/poem text from a prompt | Pay-per-token; covered by the account's promotional credit, not Always-Free (see §9) |
| **AWS Lambda** | Runs the backend logic: builds the prompt, calls Bedrock, shapes the response | Always Free: 1M requests + 400,000 GB-seconds/month |
| **Amazon S3 + CloudFront** *(or Amplify Hosting)* | Hosts and serves the static frontend | S3: 5 GB storage tier; CloudFront: Always Free 1 TB transfer/month |
| **Amazon DynamoDB** *(P1)* | Stores generated creations for the gallery view | Always Free: 25 GB storage + 25 RCU/WCU (provisioned mode) |
| **Amazon CloudWatch Logs** | Captures Lambda execution logs for debugging | Included automatically with Lambda; small free allowance |
| **Amazon Polly** *(P2, optional)* | Text-to-speech read-aloud, if you want a second AI service to name in the article instead of the browser's built-in speech synthesis | Free tier: several million characters/month for the first 12 months |

Only Bedrock is required to satisfy "at least one AWS service" — but Lambda plus S3/CloudFront (or Amplify) is close to zero extra effort and makes the AWS-usage story in the article much stronger, since it shows a real serverless pipeline rather than a single API call.

## 3. High-level data flow

1. Browser requests `/` → CloudFront → S3 returns `index.html`, `style.css`, `app.js`.
2. Visitor fills the form and clicks Generate → `app.js` does `fetch(LAMBDA_URL, { method: "POST", body: JSON.stringify(inputs) })`.
3. Lambda validates/sanitizes input, builds a system + user prompt, calls Bedrock's `Converse` API with `amazon.nova-2-lite-v1:0`.
4. Bedrock returns generated text → Lambda parses out a title + body, optionally writes an item to DynamoDB, returns JSON to the browser.
5. `app.js` renders the result with a short reveal animation.
6. *(P1)* A `/gallery` GET route (or a second Lambda) queries DynamoDB for recent creations and returns them for a gallery page.

## 4. Frontend design

**Choice: plain HTML/CSS/vanilla JS, no build step.** Reasoning: fastest to get onto S3/Amplify with zero tooling, easiest for a coding agent to generate correctly in one pass, and this app has no state complex enough to need a framework. (If the coding agent strongly prefers React, that's fine too — it doesn't change anything else in this doc, since the contract with the backend is just a JSON HTTP call.)

- `index.html` — the generator page (form + result area)
- `style.css` — playful but clean styling; a mood-based accent color shift is a nice P2 touch
- `app.js` — form handling, fetch to Lambda, render result, loading/error states
- `gallery.html` *(P1)* — lists recent creations from a `/gallery` endpoint

State is minimal: current form values, loading boolean, last result. No routing library needed for two static pages.

## 5. Backend design

### 5.1 Lambda function: `generate_handler`

- **Runtime:** Python 3.12 (boto3 ships with the Bedrock runtime client already; no extra dependencies needed for the P0 path)
- **Trigger:** Lambda function URL with CORS enabled (`Access-Control-Allow-Origin` scoped to the CloudFront/Amplify domain in production; `*` is fine for local testing)
- **Memory/timeout:** 256 MB is plenty; set timeout to 15s (generation should finish well under that)

### 5.2 Request schema

```json
{
  "name": "Aanya",
  "theme": "a rainy afternoon in a bookshop",
  "mood": "whimsical",
  "format": "poem",
  "length": "short"
}
```
All fields optional except `format`; sensible defaults fill in the rest.

### 5.3 Response schema

```json
{
  "id": "a1b2c3d4-...",
  "title": "The Umbrella That Learned to Dance",
  "text": "...",
  "format": "poem",
  "createdAt": 1755000000
}
```
On failure: `{ "error": "short, human-readable message" }` with a 4xx/5xx status.

### 5.4 Handler skeleton (Python, Bedrock Converse API)

This is a starting skeleton, not finished production code — flesh out validation, error handling, and the DynamoDB write per the priorities in the PRD.

```python
import json, os, re, time, uuid
import boto3

REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-2-lite-v1:0")
TABLE_NAME = os.environ.get("TABLE_NAME")  # unset until the P1 gallery is built

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

MOODS = {"whimsical", "adventurous", "cozy", "mysterious", "funny", "romantic", "bittersweet"}

def sanitize(text, max_len):
    text = re.sub(r"[^\w\s.,!?'\"-]", "", text or "").strip()
    return text[:max_len]

def build_prompt(name, theme, mood, fmt, length):
    word_budget = "80-150 words" if length == "short" else "180-280 words"
    system_prompt = (
        "You are Inkling, a warm and playful creative-writing companion. "
        f"You write short, original {fmt}s that are family-friendly, positive, "
        "and a little bit magical. Never include violence, hate, or adult content. "
        f"Stay within {word_budget}. "
        "Always respond with a short charming title on the first line, "
        "then a blank line, then the piece itself — nothing else."
    )
    user_prompt = (
        f"Write a {mood} {fmt} starring or dedicated to '{name}', "
        f"inspired by this theme: '{theme}'."
    )
    return system_prompt, user_prompt

def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Malformed request body."})

    name = sanitize(body.get("name") or "a curious traveler", 60)
    theme = sanitize(body.get("theme") or "a rainy afternoon", 100)
    mood = body.get("mood") if body.get("mood") in MOODS else "whimsical"
    fmt = "story" if body.get("format") == "story" else "poem"
    length = "medium" if body.get("length") == "medium" else "short"

    system_prompt, user_prompt = build_prompt(name, theme, mood, fmt, length)

    try:
        result = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": 500, "temperature": 0.95, "topP": 0.9},
        )
        raw = result["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:
        print("Bedrock error:", e)
        return _response(502, {"error": "Inkling got a little tongue-tied. Try again?"})

    title, _, piece = raw.partition("\n\n")
    if not piece:
        title, piece = "Untitled", raw

    item = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "text": piece.strip(),
        "format": fmt,
        "createdAt": int(time.time()),
    }

    # P1: uncomment once the DynamoDB table exists
    # if TABLE_NAME:
    #     save_creation(item, name, theme, mood)

    return _response(200, item)

def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        },
        "body": json.dumps(payload),
    }
```

### 5.5 Model choice

Use **`amazon.nova-2-lite-v1:0`** (Amazon's current-generation cost-effective model, GA since December 2025) as the default — good creative-writing quality, 1M-token context window (far more than needed here), cheap per generation. If Nova 2 Lite isn't yet enabled in your account/region, **`amazon.nova-micro-v1:0`** (the earlier text-only model) is a fine fallback for pure text generation at an even lower cost. Both are called the same way through the Converse API, so switching is a one-line env var change. Cross-region inference IDs (e.g. `us.amazon.nova-2-lite-v1:0`) may be required depending on your region — check what the Bedrock console shows you after requesting access.

### 5.6 Prompt design

Keeping the safety and tone instructions in the **system** prompt (not just the user prompt) is what makes the "family-friendly by construction" requirement in PRD §7.4 actually hold up — see the `build_prompt` function above for the exact template. `temperature≈0.95` and `topP≈0.9` are set deliberately high for creative variety; lower them if outputs feel too erratic during testing.

### 5.7 Read-aloud (P2)

Two honest options:
- **Browser `SpeechSynthesis` API** — zero backend work, zero cost, works today. Downside: it's not an AWS service, so it doesn't add to the AWS-usage story.
- **Amazon Polly** — call `polly.synthesize_speech(...)` from the same Lambda (or a second one), return an audio stream or a presigned S3 URL to the generated MP3. Adds genuine AWS surface area for the article, and Polly's free tier is generous, but it's more moving parts for a P2 item — only take this route if there's time left after P0/P1.

## 6. Data model — DynamoDB (P1)

**Table:** `InklingCreations`
**Design:** single-table, partition key groups all items under one logical "gallery," sort key gives chronological order for free.

| Attribute | Type | Notes |
|-----------|------|-------|
| `PK` | String | Always `"GALLERY"` for v1 (simple — revisit if this ever needs sharding) |
| `SK` | String | `"<ISO timestamp>#<creationId>"` — sorts newest-last by default; query with `ScanIndexForward=False` for newest-first |
| `creationId` | String (UUID) | Same as the `id` returned to the client |
| `title` | String | Generated title |
| `outputText` | String | The generated poem/story |
| `format` | String | `"poem"` or `"story"` |
| `mood` | String | The mood tag used |
| `createdAt` | Number | Unix timestamp |

Sample item:
```json
{
  "PK": "GALLERY",
  "SK": "2026-08-14T10:32:00Z#a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "creationId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "The Umbrella That Learned to Dance",
  "outputText": "...",
  "format": "poem",
  "mood": "whimsical",
  "createdAt": 1755000000
}
```

Billing mode: `PAY_PER_REQUEST` (on-demand) is simplest and, at hackathon-demo traffic, costs fractions of a cent — but it technically sits outside the strict Always-Free allowance, which only covers `PROVISIONED` mode. If you want a guaranteed $0, create the table with `PROVISIONED` billing and 5 RCU / 5 WCU instead; either is fine for this project's scale.

## 7. IAM & security

**Lambda execution role — least privilege policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeNovaModel",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-2-lite-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0"
      ]
    },
    {
      "Sid": "WriteCreationsTable",
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:Query"],
      "Resource": "arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/InklingCreations"
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:ACCOUNT_ID:*"
    }
  ]
}
```
Drop the `WriteCreationsTable` statement entirely until the P1 gallery is actually built.

Other notes:
- No API keys anywhere — Bedrock and DynamoDB access both flow through the Lambda's IAM role, so there's nothing secret to leak in the frontend bundle.
- CORS on the function URL should ultimately be scoped to the real frontend origin, not `*`, once the CloudFront/Amplify domain is known.
- Input length limits (see `sanitize()` in §5.4) exist mainly to keep prompts small and cheap, not as a security boundary — Bedrock's own content handling covers the safety side.

## 8. Deployment plan

**Console-first, since that's fastest for a short build window:**

1. **Request Bedrock model access first.** In the Bedrock console → Model access, request access to Amazon Nova 2 Lite (and Nova Micro as a fallback) in `us-east-1`. This is the single most commonly forgotten step and blocks everything else until it's approved (usually near-instant for Amazon's own models).
2. Create the DynamoDB table (skip if doing P0 only).
3. Create the Lambda function (Python 3.12), paste in the handler, attach the IAM role from §7, set environment variables (`MODEL_ID`, `BEDROCK_REGION`, `TABLE_NAME` if used).
4. Enable a **function URL** on the Lambda, auth type `NONE` for a public demo, CORS configured.
5. Test the function URL directly with `curl` before touching the frontend:
   ```
   curl -X POST https://<your-function-url> \
     -H "Content-Type: application/json" \
     -d '{"name":"Aanya","theme":"a rainy afternoon","mood":"whimsical","format":"poem"}'
   ```
6. Build the frontend, point `app.js` at the function URL, test locally.
7. Create an S3 bucket, enable static website hosting (or use **AWS Amplify Hosting** instead of steps 7–8 for a simpler git-push deploy with HTTPS and a CDN included out of the box).
8. Put a CloudFront distribution in front of the S3 bucket for HTTPS + caching.
9. Smoke-test the whole flow end to end from the public URL, across a few different moods/formats.

**Optional infrastructure-as-code**, if reproducibility matters more than speed — a minimal AWS SAM skeleton:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  GenerateFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: app.handler
      Runtime: python3.12
      MemorySize: 256
      Timeout: 15
      Environment:
        Variables:
          MODEL_ID: amazon.nova-2-lite-v1:0
          BEDROCK_REGION: us-east-1
      Policies:
        - Statement:
            - Effect: Allow
              Action: [bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream]
              Resource: '*'
      FunctionUrlConfig:
        AuthType: NONE
        Cors:
          AllowOrigins: ['*']
          AllowMethods: ['POST']
```

**Region:** `us-east-1` (N. Virginia) is recommended for the widest Bedrock Nova model availability.

## 9. Free tier & cost mapping

The challenge prompt mentions up to **$200 in Free Tier credits for new AWS accounts** — under AWS's current account model (in effect since mid-2025), new accounts get a credit balance (up to $200) plus the separate "Always Free" service allowances below, which don't draw down that balance at all.

| Service | Always-Free allowance | Expected use for this project | Likely cost |
|---------|------------------------|-------------------------------|-------------|
| Lambda | 1M requests + 400,000 GB-seconds/month | A few hundred invocations during dev + demo | $0 |
| DynamoDB | 25 GB + 25 RCU/WCU (provisioned mode) | A handful of small items | $0 |
| S3 | 5 GB standard storage (new-account tier) | A few KB of static files | $0 |
| CloudFront | 1 TB transfer + 10M requests/month | Negligible for a demo | $0 |
| CloudWatch | 10 metrics, 10 alarms, 1M API requests/month | Default Lambda logs | $0 |
| **Bedrock (Nova 2 Lite)** | **Not part of Always-Free** — billed per input/output token | A few hundred short generations | A few cents to low dollars, drawn from the $200 credit |
| Route 53 (if a custom domain is wanted) | Not free — ~$0.50/month per hosted zone | Optional, skip it | Skip unless wanted |

Set a low-threshold **AWS Budget alert** (e.g. $5) right after account setup so nothing surprises you mid-build.

## 10. Error handling & edge cases

- Empty form submission → defaults kick in (see §5.4), never a hard error
- Bedrock throttling (`ThrottlingException`) → one retry with a short backoff, then the friendly fallback message from §5.4
- Network failure client-side → inline error under the button with a "try again" affordance, form values preserved
- Unexpected/malformed Bedrock output (missing the title/blank-line convention) → fall back to `title="Untitled"`, full response as the body, rather than erroring out
- Overlong user input → truncated silently by `sanitize()` before it ever reaches the prompt

## 11. Testing plan

Manual QA checklist before submission:
- [ ] Generate at least one piece per mood (7 total) and skim for tone/quality
- [ ] Try both `poem` and `story` formats
- [ ] Submit with every field blank — defaults should produce a sensible result
- [ ] Try a very long theme string — should truncate gracefully, not error
- [ ] Reload the page and confirm a fresh session still works (no stale state issues)
- [ ] Test on a phone-width browser window
- [ ] *(P1)* Confirm the gallery shows newly generated items after a refresh
- [ ] *(P2)* Confirm read-aloud actually plays audio

## 12. Suggested repo structure

```
inkling/
├── frontend/
│   ├── index.html
│   ├── gallery.html        # P1
│   ├── style.css
│   └── app.js
├── backend/
│   └── generate_handler.py
├── infra/
│   └── template.yaml        # optional SAM template, §8
├── PRD.md
├── TDD.md
└── README.md                 # setup + deploy steps, screenshots, live link
```

## 13. Implementation checklist (ordered, for whoever codes this)

**P0 — must ship to pass evaluation**
1. [ ] Request Bedrock Nova model access in the console
2. [ ] Write and test `generate_handler.py` locally against Bedrock (CLI/console test event)
3. [ ] Deploy the Lambda + function URL, verify with `curl`
4. [ ] Build `index.html` / `style.css` / `app.js` against the PRD §7.1–7.2 spec
5. [ ] Deploy the frontend to S3+CloudFront or Amplify Hosting
6. [ ] End-to-end test from the public URL
7. [ ] Capture screenshots/short demo video
8. [ ] Write the article (≥500 words, covers every required section, names the AWS services — see PRD §14 for the open item on confirming the exact section list)

**P1 — strengthens the submission**
9. [ ] Create the DynamoDB table, wire up the save-on-generate call
10. [ ] Build `gallery.html` + a `/gallery` read path
11. [ ] Add regenerate/copy buttons and a small reveal animation

**P2 — polish if time remains**
12. [ ] Read-aloud (browser speech synthesis or Amazon Polly)
13. [ ] Mood-based visual accents / a bit of confetti on generate
14. [ ] AWS Budget alert set up

## 14. Appendix — quick reference

- Bedrock Converse API docs pattern: `bedrock.converse(modelId=..., system=[...], messages=[...], inferenceConfig={...})`
- Model IDs: `amazon.nova-2-lite-v1:0` (primary), `amazon.nova-micro-v1:0` (fallback)
- Function URL CORS header needed on every response, including error responses: `Access-Control-Allow-Origin`
- DynamoDB table name: `InklingCreations`, PK `"GALLERY"`, SK `"<timestamp>#<uuid>"`
