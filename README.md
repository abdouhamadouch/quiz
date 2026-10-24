# Telegram Quiz Bot

A Telegram bot for creating AI-generated quizzes from a lesson or a topic, reviewing via native Telegram quiz polls, and running timed competitive exams.

## Features

- `/quiz`: reply to a lesson message to use it as the source, or start a guided setup with an optional topic and source text.
- Choose 5/10/15/20 questions, easy/medium/hard difficulty, question timer, and usage mode from inline buttons.
- AI question generation with Groq/Gemini failover and JSON validation.
- **Review one by one:** native Telegram quiz polls with correct-answer feedback; the creator or a group admin manually presses **السؤال التالي**.
- **Publish all polls:** `/publishquiz ID` sends every saved quiz question as a native quiz poll at once.
- **Competitive exam:** inline answers, per-question timer, 10 points for a correct answer, and final ranking in groups.
- Personal saved quiz library: `/library`.
- Share a saved quiz into a group as a draft using `/sharequiz ID`; it does not start immediately. A group admin or bot owner explicitly starts it with `/startquiz`.
- Use saved quizzes for review with `/reviewquiz ID` or publish all their polls with `/publishquiz ID`.
- `/end` or `/stop`: end the active session; `/cancel`: cancel an active session.
- `/leaderboard` and `/reset` for saved scores.
- SQLite persistence and a `/health` endpoint for Render.

## Commands

- `/quiz` — create a quiz. If replying to a text lesson, the lesson is used directly.
- `/skip` — skip the current optional topic/source setup step.
- `/library` — list the latest saved quizzes and their IDs.
- `/sharequiz ID` — publish your saved quiz to a group as a waiting exam draft.
- `/startquiz` — start the waiting group exam (bot owner/group admins only).
- `/reviewquiz ID` — start manual, one-poll-at-a-time review.
- `/publishquiz ID` — publish all saved quiz polls at once.
- `/end`, `/stop` — end the active session.
- `/cancel` — cancel the active session.
- `/leaderboard` — show saved scores.
- `/reset` — clear scores in the current chat (bot owner/group admins only).

## Required environment variables

- `BOT_TOKEN`: token from BotFather.
- `GROQ_API_KEY`: Groq API key.
- `GEMINI_API_KEY`: Google Gemini API key.
- `OWNER_IDS`: comma-separated Telegram numeric user IDs authorized to control the bot. Group administrators can start/stop group exams.
- Optional model settings: `GROQ_MODEL`, `GEMINI_MODEL`.
- `DATABASE_PATH`: SQLite path. Render Blueprint sets this to `data/quizbot.sqlite3`.

Never commit real tokens or API keys.

## Deploy to Render

1. Open the `abdouhamadouch/quiz` repository and confirm the files are on `main`.
2. In Render choose **New → Blueprint**, then connect this repository.
3. Add the real values for `BOT_TOKEN`, `GROQ_API_KEY`, `GEMINI_API_KEY`, and `OWNER_IDS`.
4. Render installs `requirements.txt` and starts `python bot.py`.
5. Verify `/health`, then send `/start` to the bot.

The Blueprint uses SQLite on the local filesystem. Render's free filesystem is ephemeral, so saved quizzes and scores may be lost on restart/redeploy unless a persistent disk or managed database is configured. Active sessions and waiting group drafts are in memory and do not survive process restarts.

## Important behavior and limitations

- Telegram native quiz polls reveal correctness according to Telegram's poll UI. Telegram does not provide the bot with a reliable list of every group member, so the manual review mode intentionally advances only when its **السؤال التالي** button is pressed.
- The publish-all mode sends all quiz polls at once and then ends the bot's active review session; it does not calculate competitive rankings.
- Group exams wait for `/startquiz` after `/sharequiz ID`. Stop/end controls are restricted to the bot owner or group admins.
- Text and text captions are supported as source material. OCR, voice transcription, PDF/DOCX import, and image-based question generation are not implemented yet.
- AI-generated questions should be reviewed before use in high-stakes exams. Live testing with a real Telegram bot token and configured AI keys is still required.

## Local run

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Automated checks

GitHub Actions compiles the Python modules and runs unit tests on pushes and pull requests to `main`.
