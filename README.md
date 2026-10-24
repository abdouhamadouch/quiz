# Telegram Quiz Bot

A separate Telegram quiz bot built with Python and `python-telegram-bot`. It creates multiple-choice questions from replied-to lesson text using Groq and Gemini, supports private and group quizzes, timed answers, scoring, and persistent leaderboards.

## Features

- `/quiz 5 20` in reply to a text lesson: generate 5 questions with 20 seconds per question.
- AI provider failover: tries Groq and then Gemini (or the reverse after a successful request); malformed AI output is rejected.
- Four inline answer choices, one answer per participant per question, and time limits.
- Private practice advances after the learner answers; group quizzes let participants answer until the timer expires.
- `/end` or `/stop`: end the current quiz and save its scores.
- `/cancel`: cancel the active quiz without saving that session's scores.
- `/reset`: clear the conversation's saved leaderboard.
- `/leaderboard`: display saved scores.
- SQLite leaderboard and `/health` endpoint for Render health checks.

## Required environment variables

- `BOT_TOKEN`: token from BotFather.
- `GROQ_API_KEY`: Groq API key.
- `GEMINI_API_KEY`: Google Gemini API key.
- `OWNER_IDS`: comma-separated Telegram numeric user IDs authorized to control the bot. Group administrators are also allowed to use admin commands.
- Optional model settings: `GROQ_MODEL`, `GEMINI_MODEL`.
- `DATABASE_PATH`: SQLite path. Render Blueprint sets this to `/var/data/quizbot.sqlite3`.

Never commit real tokens or API keys.

## Deploy to Render

1. Open the `abdouhamadouch/quiz` repository and confirm the files are on `main`.
2. In Render choose **New → Blueprint**, then connect this repository.
3. Add the real values for `BOT_TOKEN`, `GROQ_API_KEY`, `GEMINI_API_KEY`, and `OWNER_IDS` in the Render environment settings.
4. Render reads `render.yaml`, installs `requirements.txt`, and starts `python bot.py`.
5. Verify the service health endpoint at `/health` and then send `/start` to the Telegram bot.

The Blueprint uses local SQLite so it can be tried on a free web service, but the local filesystem is ephemeral: leaderboard data may be lost when Render restarts or redeploys the service. For durable production results, attach a supported persistent disk on an eligible paid plan or migrate the database layer to managed PostgreSQL. Render free web services may sleep when idle, so they are not a guarantee of uninterrupted 24/7 bot availability.

## Group setup

- Add the bot to the group.
- To let the bot see lesson messages and reply-trigger commands reliably, review BotFather's Group Privacy setting. If privacy mode is enabled, Telegram may limit which messages the bot receives.
- Promote the bot to administrator if Telegram permissions are needed for your group configuration.

## Current limitations

- Lesson source currently needs to be text or a text caption; OCR, voice transcription, PDF/DOCX import, and media-based question cards are not yet implemented.
- Active quiz sessions are held in memory and will not resume after a process restart. Saved leaderboards persist on the configured disk.
- A single active quiz per chat is supported.
- AI-generated questions should be reviewed before being used for high-stakes exams.
- This is an initial deployable version; it still needs live testing with a real Telegram bot token and configured AI keys.

## Local run

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill .env values, then load them into your shell or use your preferred env loader.
python bot.py
```
