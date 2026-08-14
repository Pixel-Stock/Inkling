# Handoff prompt

Paste this into a new conversation with your coding agent, along with `PRD.md` and `TDD.md` attached.

---

I'm building **Inkling**, a small AWS-hosted web app for a hackathon challenge: type a name, a theme, and a mood, and get back an original short poem or story written live by an AI model. I've attached a full PRD and TDD — please read both before writing any code.

Build it in this order:

1. **P0 first, all of it** — this is the whole pass/fail bar for the submission (see PRD §13 "Definition of done" and TDD §13 "Implementation checklist"). Don't start on P1/P2 until every P0 box is checked.
2. Follow the TDD's architecture exactly: static frontend (plain HTML/CSS/JS) on S3+CloudFront or Amplify Hosting, a Python Lambda behind a function URL, calling Amazon Bedrock's `amazon.nova-2-lite-v1:0` model via the Converse API.
3. Use the handler skeleton in TDD §5.4 as your starting point, but write it out properly — real input validation, real error handling, not just the happy path.
4. Before deploying anything, make sure Bedrock model access has been requested/approved in the AWS console (TDD §8, step 1) — this blocks everything downstream.
5. After the P0 path works end to end (live URL, generates real output, screenshots taken), move to P1 (DynamoDB gallery, regenerate/copy buttons) and only then P2 (read-aloud, small animations) if there's time left.
6. Flag anything in the PRD's open questions (§14) that you need me to confirm — especially the exact article section requirements and the real deadline, since those weren't fully specified.
7. When you're done with the app, help me draft the ≥500-word article the challenge requires, covering whatever sections it asks for and clearly naming every AWS service we used and why.

Ask me anything you need clarified before you start, but otherwise just build — I want a working, deployed, screenshot-able demo, not just code.
