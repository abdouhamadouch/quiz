# Telegram Quiz Bot

Telegram bot for generating educational multiple-choice quizzes from lesson text, PDF/DOCX/TXT files, images, or a general topic. It supports private practice, group competitions, Telegram quiz polls, a personal library, and saved results.

## Features

- AI question generation with Groq/Gemini failover; validates four distinct options, answer indexes, duplicate questions, and the requested question count.
- Quiz settings: 5/10/15/20 questions, easy/medium/hard, 10–60 second timer, and competitive/manual-review/publish-all modes.
- Source input: reply to text/caption or upload PDF, DOCX, TXT, or a clear image. PDF extraction supports text-based PDFs; scanned PDFs should be sent as images. Image text extraction uses Gemini and requires GEMINI_API_KEY.
- Library management: /library, /searchquiz, /previewquiz, /deletequiz (confirmation and ownership check), /copyquiz, /renamequiz, /editquiz, and /setcategory. Categories are searchable.
- /stats shows personal saved-quiz totals and accumulated group score statistics. Common Arabic text aliases are supported for starting a quiz, opening the library, viewing the leaderboard, and opening personal statistics.
- /sharequiz ID creates a group draft. A group admin or bot owner must run /startquiz before a competition begins. Drafts are stored in the configured database and can survive a restart.
- /reviewquiz ID advances through native quiz polls manually; /publishquiz ID publishes all polls at once.
- Timed competitive exams award 10 points per correct answer, show final rankings, and save overall and per-quiz group results. Use /quizresults ID in the group.
- /leaderboard, /reset, /end, /stop, and /cancel.
- /health endpoint for Render health checks.

## Commands

- /quiz — create a quiz from a reply, a topic, or lesson source.
- /skip — skip an optional topic/source setup step.
- /library — list your saved quizzes (private chat).
- /searchquiz WORD — search saved quiz titles/source (private chat).
- /previewquiz ID — inspect questions and answers (private chat).
- /deletequiz ID — request deletion; confirm using the inline button (private chat).
- /copyquiz ID — create an independent copy (private chat).
- /renamequiz ID NEW_TITLE — rename a saved quiz (private chat).
- /editquiz ID QUESTION_NUMBER — edit a question in private chat. Send lines in this order: question, four options, correct option number (1–4), then optional explanation.
- /setcategory ID CATEGORY — categorize a saved quiz (private chat).
- /stats — show your saved quizzes and accumulated score statistics (private chat).
- /sharequiz ID — create a waiting group draft.
- /startquiz — start the waiting group competition (owner/admin only).
- /reviewquiz ID — start manual poll review.
- /publishquiz ID — publish all saved quiz polls at once.
- /quizresults ID — show results saved for that quiz in the current group.
- /end, /stop — end an active session and save results.
- /cancel — cancel an active session, or cancel a pending setup/edit.
- /leaderboard — show the cumulative group leaderboard.
- /reset — clear cumulative scores in the current chat (owner/admin only).

## Environment variables

Required:
- BOT_TOKEN: Telegram token from BotFather.
- GROQ_API_KEY and/or GEMINI_API_KEY: AI keys; Gemini is required for image OCR.
- OWNER_IDS: comma-separated Telegram numeric IDs for bot owners.

Optional:
- GROQ_MODEL, GEMINI_MODEL.
- DATABASE_URL: PostgreSQL URL for durable hosted storage.
- DATABASE_PATH: SQLite path when DATABASE_URL is unset.
- LOG_LEVEL.

Never commit real tokens or API keys.

## Persistence and Render

SQLite remains the no-configuration default. Render's free filesystem is ephemeral, so quizzes and scores can be lost on restart/redeploy when using the default SQLite path. For durable hosted storage, configure DATABASE_URL to a PostgreSQL database. The app creates/upgrades its tables on startup.

Saved quizzes, scores, per-quiz results, and waiting group drafts are stored in the database. Live in-progress timers and answer state are held in memory and cannot safely resume after a process restart; the bot should be ended and restarted after a restart.

1. Connect this repository to Render using the Blueprint.
2. Set BOT_TOKEN, OWNER_IDS, and the AI key(s).
3. For persistence across deploys, set DATABASE_URL to a PostgreSQL connection URL. If it is unset, SQLite is used.
4. Verify /health, then test /start and quiz creation in Telegram.

## Known limitations

- PDF extraction reads embedded text; image-only/scanned PDFs are not OCRed as a whole document. Send individual pages as images instead.
- DOCX text and table cells are supported. Image OCR is performed by Gemini and may misread low-resolution or handwritten text.
- Native Telegram quiz polls show correctness according to Telegram's poll UI. Manual review intentionally advances only when the creator or an admin presses “السؤال التالي”.
- Publish-all review is not a competition and does not calculate scores.
- Live Telegram operation and real provider API calls must be tested with actual secrets before production use.

## Local run

Create a virtual environment, install requirements.txt, copy .env.example to .env, fill in real secrets, and run python bot.py.

## Automated checks

GitHub Actions compiles Python files and runs the unit tests on pushes and pull requests to main.
