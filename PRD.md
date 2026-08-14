# Product Requirements Document (PRD)
## Inkling — an AI story & poem generator

**Owner:** Mrugesh Mangesh Kulkarni
**Prepared for:** implementation handoff to a coding agent (e.g. Claude Opus 4.8 — note the current Opus model is 4.8, not 4.6; nothing here is model-specific)
**Status:** v1.0, ready to build
**Companion docs:** `TDD.md` (technical design), `HANDOFF_PROMPT.md` (paste-ready kickoff prompt)

---

## 1. Overview

Inkling is a tiny, cheerful web app that turns a few playful inputs — a name, a theme, a mood — into an original short story or poem, written live by an AI model hosted on AWS. It is built for the "build something creative" AWS challenge: a small app that makes words, images, sound, or play, deployed on AWS Free Tier.

One-line pitch: *type a name and a vibe, get a tiny piece of writing made just for you, in about five seconds.*

## 2. Background — the challenge this satisfies

This app is being built for a hackathon-style submission with a hard pass/fail bar across three categories. Everything in this PRD and the companion TDD is designed to clear all three:

| # | Category | Bar to clear |
|---|----------|--------------|
| 1 | Completeness (gate) | A 500+ word article covering every required section, plus a working app link or repo |
| 2 | Relevance & functionality | A simple app that makes something creative (words, in our case), with visible evidence it works — screenshots, video, or a live link |
| 3 | AWS service usage | At least one AWS service used, clearly described in the article |

A fail on category 1 disqualifies the whole submission regardless of categories 2–3, so the article and the live link are just as important as the code.

## 3. Goals & success metrics

| Goal | How we'll know |
|------|-----------------|
| Judges can open a link and get a poem/story in under 10 seconds | Live demo link works with no login, no setup |
| The output is genuinely fun, not a bare text box | At least one delight touch (animated reveal, playful copy, a gallery, or read-aloud) ships |
| AWS usage is real and explainable | At least Bedrock + Lambda + one hosting service are wired up and named in the article |
| Nothing costs real money | Stays inside Always-Free limits + the promotional Bedrock credit (see TDD §9) |
| The submission clears all three pass/fail categories | Definition of Done in §13 is fully checked before submitting |

## 4. Non-goals (out of scope for v1)

- No user accounts, login, or personal data storage
- No payments or monetization
- No production-scale traffic handling — this is a demo, not a product
- No multi-language support beyond whatever the model does by default
- No mobile app — responsive web only

## 5. Users

- **Primary: the judges.** They'll spend a couple of minutes per submission. The app needs to make its point almost instantly — no explanation required.
- **Secondary: anyone who clicks the link.** Friends, classmates, random visitors. The app should be fun enough that they generate a second one without being told to.

## 6. User stories

Tagged by priority — **P0** is what makes the submission pass, **P1** meaningfully strengthens it, **P2** is polish if time allows.

- **P0** — As a visitor, I can type a name/topic, pick a mood and a format (poem or story), and press one button to get an original piece of writing.
- **P0** — As a visitor, I can read the result clearly on any screen size without technical knowledge.
- **P0** — As a judge, I can tell at a glance which AWS services are doing the work (from the article, not just the code).
- **P1** — As a visitor, I can generate another one immediately without reloading the page.
- **P1** — As a visitor, I can copy or share the text I got.
- **P1** — As a visitor, I can browse a small gallery of past creations for a "hall of fame" feel.
- **P2** — As a visitor, I can hear my poem read aloud.
- **P2** — As a visitor, I see a small animation or reaction (confetti, a mood-colored background) when my piece appears.

## 7. Functional requirements

### 7.1 Input form (P0)
- **Name / dedicatee** — free text, optional, defaults to something whimsical if left blank (e.g. "a curious traveler")
- **Theme / topic** — free text, optional, defaults to something like "a rainy afternoon"
- **Mood** — a small fixed set of choices: whimsical, adventurous, cozy, mysterious, funny, romantic, bittersweet
- **Format** — poem or story (toggle)
- **Length** — short or medium (short by default, to keep generation fast and cheap)
- **Generate** button — primary call to action

### 7.2 Output (P0)
- A short, charming title generated along with the piece
- The story/poem text, clearly formatted (line breaks preserved for poems, paragraphs for stories)
- A loading state while the model is working (this should feel intentional, not like a stalled page — see TDD for the "typewriter" suggestion)
- A visible error state if generation fails, with a retry option

### 7.3 Regenerate & share (P1)
- "Generate another" button that re-runs with the same inputs (new randomness) or lets the visitor tweak inputs and go again
- "Copy text" button
- Optional "share link" if a gallery (7.5) is built

### 7.4 Content & safety (P0)
- Output must be family-friendly by construction, via the system prompt (see TDD §5.6), not by after-the-fact filtering alone
- No collection of anything sensitive — the name field is just flavor text for the story, never stored as personal data if the P1 gallery is skipped, and only stored alongside the generated text (not linked to any real identity) if the gallery ships

### 7.5 Gallery / "Hall of Fame" (P1)
- A simple list of recent creations (title + short excerpt), most recent first
- Demonstrates a second AWS service (DynamoDB) and gives judges something to click through beyond the happy path

### 7.6 Read-aloud (P2)
- A "listen" button that plays the piece back as speech
- Can be done for free with the browser's built-in speech synthesis, or via Amazon Polly if the team wants a second AI-adjacent AWS service to point to in the article — either is acceptable; see TDD §5.7 for the tradeoff

## 8. Content & tone guidelines

The generated writing should always be:
- Positive and warm by default, even for "bittersweet" or "mysterious" moods — no graphic violence, no despair without hope, nothing scary in a genuinely upsetting way
- Short enough to read in under a minute (roughly 80–180 words for a poem, 150–300 for a short story)
- Personalized enough that two people entering different names/themes get visibly different output, not a reskinned template

## 9. UX flow

1. Visitor lands on the page and sees the form front and center, with one example pre-filled or a placeholder so the empty state doesn't feel intimidating.
2. Visitor fills in what they want (or just hits Generate with defaults).
3. On submit, the button shows a short "writing your poem…" state.
4. The result appears — title, then the piece, with a small entrance animation.
5. Visitor can regenerate, copy, or (P1) see it added to the gallery.

```
┌───────────────────────────────┐
│  Inkling                       │
│  ────────────────────────────  │
│  Name/theme:  [___________]    │
│  Mood:        [dropdown]       │
│  Format:      (poem) (story)   │
│                                 │
│         [ ✦ Generate ]         │
│                                 │
│  ─── result appears below ───  │
│  "The Umbrella That Learned    │
│   to Dance"                    │
│   <poem text...>               │
│  [Copy] [Generate another]     │
└───────────────────────────────┘
```

## 10. Non-functional requirements

- **Latency:** generation should complete in under ~8 seconds for a short piece on Nova 2 Lite
- **Responsive:** usable on a phone-width screen without horizontal scrolling
- **No login:** zero-friction access for judges
- **Browser support:** latest Chrome, Firefox, Safari, Edge — no IE/legacy support needed
- **Accessibility:** sufficient color contrast, form fields with labels, loading state announced for screen readers
- **Availability:** best-effort; it only needs to be up and reachable during the judging window, but keep it live rather than tearing it down right after building it

## 11. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Bedrock model access not enabled in the AWS account (a common first-timer trap) | Request model access in the Bedrock console *before* writing any code — see TDD §8 step 1 |
| Cold-start latency on the first Lambda call makes the demo feel slow | Keep the function small and dependency-light; mention "first request may take a couple seconds longer" in the article if needed |
| Model occasionally produces an off-target or refused response | Client-side retry-once-with-a-nudge; server-side fallback message that's still charming ("Inkling got a little tongue-tied — try again?") rather than a raw error |
| Free Tier credit runs low from repeated testing | Set a low-value AWS Budget alert (see TDD §9); Nova 2 Lite is inexpensive per generation |
| Judges' link goes stale if AWS resources are torn down early | Leave the deployment running through the full judging window |
| Scope creep eating the time budget | P0 list in §6 is the actual bar for passing; P1/P2 are explicitly optional |

## 12. Timeline (adjust to your actual deadline — none was specified)

- **Day 1:** AWS setup (account, Bedrock model access, IAM), Lambda function calling Bedrock, tested via CLI/console — no frontend yet
- **Day 2:** Frontend built and wired to the Lambda function URL, deployed to S3/CloudFront or Amplify Hosting, end-to-end demo working
- **Day 3:** Polish (P1/P2 items as time allows), screenshots/demo video captured, article written, final QA pass against §13

## 13. Definition of done (crosswalked to the evaluation)

- [ ] App is a working story/poem generator — visitor can generate original text on demand *(Category 2)*
- [ ] Live URL (or repo with clear run instructions) is up and reachable *(Category 1)*
- [ ] Screenshots or a short demo video captured showing generation happening *(Category 2)*
- [ ] At least one AWS service is genuinely doing work (Bedrock at minimum; Lambda + S3/CloudFront or Amplify round it out) *(Category 3)*
- [ ] Article is written, ≥500 words, and names every AWS service used and what it does *(Category 1 & 3)*
- [ ] Article covers every section the challenge's article requirements ask for (confirm the exact list from the challenge page, since it wasn't fully pasted into this PRD — see §14)
- [ ] Nothing in the generated output is off-tone (ran a handful of test generations across all moods)
- [ ] Deployment is left running for the judging window

## 14. Assumptions & open questions

- The exact **article requirements** (the specific sections it must cover) weren't included in what was shared for this PRD — only the pass/fail categories were. Confirm the full article checklist from the challenge page before writing it, and check it off in §13.
- **Deadline** wasn't specified — the timeline in §12 is a 3-day placeholder; compress or stretch it to fit the real one.
- Assumed **AWS region us-east-1 (N. Virginia)** for best Bedrock model availability — confirm this still fits if the account/team has a different default region.
- Assumed the team is comfortable with a small amount of AWS console work (enabling model access can't be fully scripted) — flag if a fully hands-off deployment is required instead.
