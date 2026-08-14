# Inkling ✦

**Inkling** is a cozy, literary workspace powered by Amazon Bedrock. Type a name, a theme, and a mood, and get back an original short poem or story written live by an AI model.

Created for the **AWS Builder Center Weekend Challenge: Build a Creative App**.

## Architecture
- **Frontend**: Vanilla HTML/CSS/JS (no framework required). Designed with a dual-pane workspace aesthetic.
- **Backend**: AWS Lambda (Python 3.12) using a Function URL.
- **AI Engine**: Amazon Bedrock (`amazon.nova-2-lite-v1:0`).

## Running Locally
1. Install dependencies for the local mock server:
   ```bash
   npm install
   ```
2. Start the local server:
   ```bash
   npm start
   ```
3. Open `http://localhost:3000` in your browser.
