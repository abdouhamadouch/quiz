"""Telegram quiz bot. Python 3.11+, python-telegram-bot v21+."""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ai_provider import generate_questions
from db import init_db, leaderboard, reset_chat, save_session_scores

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("quizbot")
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_IDS = {int(v) for v in os.getenv("OWNER_IDS", "").split(",") if v.strip().isdigit()}
MAX_QUESTIONS = 20
MIN_SECONDS, MAX_SECONDS = 10, 60
sessions: dict[int, dict] = {}
sessions_lock = asyncio.Lock()

def group_chat(chat_type: str) -> bool:
    return chat_type in (ChatType.GROUP, ChatType.SUPERGROUP)

async def authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user, chat = update.effective_user, update.effective_chat
    if not user or not chat:
        return False
    if user.id in OWNER_IDS:
        return True
    if not group_chat(chat.type):
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🎓 بوت الاختبارات التعليمية\n\n"
        "ردّ على رسالة تحتوي درسًا أو قائمة كلمات بالأمر:\n"
        "/quiz 5 20\n\n"
        "العدد الأقصى 20 سؤالًا، والوقت من 10 إلى 60 ثانية لكل سؤال.\n"
        "/leaderboard — لوحة المتصدرين\n"
        "/end أو /stop — إنهاء الاختبار وحفظ النتائج\n"
        "/cancel — إلغاء الاختبار دون حفظ نقاط الجلسة\n"
        "/reset — مسح نتائج هذه المحادثة"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not msg or not chat or not user:
        return
    args = context.args
    try:
        count = max(1, min(MAX_QUESTIONS, int(args[0]))) if args else 5
    except ValueError:
        count = 5
    try:
        seconds = max(MIN_SECONDS, min(MAX_SECONDS, int(args[1]))) if len(args) > 1 else 20
    except ValueError:
        seconds = 20

    source = ""
    if msg.reply_to_message:
        source = msg.reply_to_message.text or msg.reply_to_message.caption or ""
        if not source and (msg.reply_to_message.photo or msg.reply_to_message.document or
                           msg.reply_to_message.audio or msg.reply_to_message.voice):
            await msg.reply_text("استخرج النص من الوسائط أولًا ثم أرسل /quiz ردًا على النص.")
            return
    if not source:
        await msg.reply_text("استعمل الأمر ردًا على رسالة الدرس، مثل: /quiz 5 20")
        return
    if len(source.strip()) < 20:
        await msg.reply_text("النص قصير جدًا. أرسل درسًا أو قائمة مفردات فيها معلومات كافية.")
        return
    async with sessions_lock:
        if chat.id in sessions:
            await msg.reply_text("يوجد اختبار نشط في هذه المحادثة. أنهِه بـ /end أو ألغِه بـ /cancel.")
            return

    status = await msg.reply_text("⏳ جارٍ إعداد الأسئلة من الدرس…")
    try:
        questions, provider = await asyncio.to_thread(generate_questions, source, count)
    except Exception:
        log.exception("AI generation failed")
        await status.edit_text("تعذّر إنشاء الأسئلة من المزودين. تحقق من مفاتيح Groq وGemini ثم حاول مجددًا.")
        return

    session = {
        "chat_id": chat.id, "chat_type": chat.type, "creator_id": user.id,
        "questions": questions, "seconds": seconds, "index": 0,
        "scores": {}, "answered": set(), "message_id": None,
        "timer": None, "provider": provider,
    }
    async with sessions_lock:
        if chat.id in sessions:
            await status.edit_text("بدأ اختبار آخر أثناء التحضير؛ لم أبدأ اختبارًا مكررًا.")
            return
        sessions[chat.id] = session
    await status.edit_text(f"تم إعداد {len(questions)} أسئلة باستخدام {provider}. يبدأ الاختبار الآن.")
    await post_question(context, session)

async def post_question(context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    chat_id = session["chat_id"]
    index = session["index"]
    if index >= len(session["questions"]):
        await finish(context, chat_id, cancelled=False)
        return
    q = session["questions"][index]
    session["answered"] = set()
    keyboard = [[InlineKeyboardButton(option, callback_data=f"ans:{chat_id}:{index}:{i}")]
                for i, option in enumerate(q["options"])]
    try:
        sent = await context.bot.send_message(
            chat_id,
            f"❓ السؤال {index + 1}/{len(session['questions'])}\n"
            f"⏱ الوقت: {session['seconds']} ثانية\n\n{q['question']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        session["message_id"] = sent.message_id
    except Exception:
        log.exception("Unable to post question")
        sessions.pop(chat_id, None)
        return
    session["timer"] = asyncio.create_task(timeout_question(context, chat_id, index, session["seconds"]))

async def timeout_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int, index: int, seconds: int) -> None:
    try:
        await asyncio.sleep(seconds)
        session = sessions.get(chat_id)
        if not session or session["index"] != index:
            return
        q = session["questions"][index]
        try:
            await context.bot.edit_message_reply_markup(chat_id, session["message_id"], reply_markup=None)
            await context.bot.send_message(
                chat_id,
                f"⏰ انتهى الوقت. الإجابة الصحيحة: {q['options'][q['answer']]}\n{q.get('explanation', '')}".strip(),
            )
        except Exception:
            log.exception("Unable to send timeout feedback")
        session["index"] += 1
        await asyncio.sleep(1)
        await post_question(context, session)
    except asyncio.CancelledError:
        return

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    try:
        _, chat_raw, index_raw, option_raw = query.data.split(":")
        chat_id, index, option = int(chat_raw), int(index_raw), int(option_raw)
    except (ValueError, AttributeError):
        await query.answer("زر غير صالح.", show_alert=True)
        return
    session = sessions.get(chat_id)
    if not session or session["index"] != index:
        await query.answer("انتهى هذا السؤال.", show_alert=True)
        return
    user = query.from_user
    if user.id in session["answered"]:
        await query.answer("سُجّلت إجابتك بالفعل.")
        return
    q = session["questions"][index]
    if option not in range(4):
        await query.answer("اختيار غير صالح.", show_alert=True)
        return
    session["answered"].add(user.id)
    score = session["scores"].setdefault(user.id, {
        "name": user.full_name, "points": 0, "correct": 0, "answered": 0
    })
    score["name"] = user.full_name
    score["answered"] += 1
    correct = option == q["answer"]
    if correct:
        score["points"] += 10
        score["correct"] += 1
    await query.answer("✅ صحيح! +10 نقاط" if correct else "❌ إجابة غير صحيحة", show_alert=True)

    if group_chat(session["chat_type"]):
        try:
            feedback = "إجابة صحيحة (+10 نقاط)" if correct else "إجابة غير صحيحة"
            await context.bot.send_message(chat_id, f"{user.full_name}: {feedback}")
        except Exception:
            log.exception("Unable to post group answer feedback")

    if session["chat_type"] == ChatType.PRIVATE:
        timer = session.get("timer")
        if timer:
            timer.cancel()
        try:
            await context.bot.edit_message_reply_markup(chat_id, session["message_id"], reply_markup=None)
            explanation = q.get("explanation", "")
            await context.bot.send_message(
                chat_id,
                f"{'✅ إجابة صحيحة' if correct else '❌ الإجابة الصحيحة: ' + q['options'][q['answer']]}\n{explanation}".strip(),
            )
        except Exception:
            log.exception("Unable to send private feedback")
        session["index"] += 1
        await post_question(context, session)

async def finish(context: ContextTypes.DEFAULT_TYPE, chat_id: int, cancelled: bool) -> None:
    session = sessions.pop(chat_id, None)
    if not session:
        return
    timer = session.get("timer")
    if timer and timer is not asyncio.current_task():
        timer.cancel()
    if cancelled:
        await context.bot.send_message(chat_id, "🗑️ أُلغي الاختبار ولم تُحفظ نقاط هذه الجلسة.")
        return
    save_session_scores(chat_id, session["scores"])
    rows = leaderboard(chat_id, 10)
    lines = ["🏆 النتائج النهائية", f"الأسئلة: {len(session['questions'])}"]
    if not rows:
        lines.append("لم تُسجّل أي إجابات.")
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            label = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{label} {row['name']} — {row['points']} نقطة ({row['correct']}/{row['answered']} صحيحة)")
    await context.bot.send_message(chat_id, "\n".join(lines))

async def end_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await authorized(update, context):
        await update.effective_message.reply_text("هذا الأمر متاح للمالك أو مشرفي المجموعة فقط.")
        return
    if update.effective_chat.id not in sessions:
        await update.effective_message.reply_text("لا يوجد اختبار نشط.")
        return
    await finish(context, update.effective_chat.id, cancelled=False)

async def cancel_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await authorized(update, context):
        await update.effective_message.reply_text("هذا الأمر متاح للمالك أو مشرفي المجموعة فقط.")
        return
    if update.effective_chat.id not in sessions:
        await update.effective_message.reply_text("لا يوجد اختبار نشط.")
        return
    await finish(context, update.effective_chat.id, cancelled=True)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await authorized(update, context):
        await update.effective_message.reply_text("هذا الأمر متاح للمالك أو مشرفي المجموعة فقط.")
        return
    chat_id = update.effective_chat.id
    if chat_id in sessions:
        await finish(context, chat_id, cancelled=True)
    reset_chat(chat_id)
    await update.effective_message.reply_text("تم مسح نتائج هذه المحادثة وإعادة ضبطها.")

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = leaderboard(update.effective_chat.id)
    if not rows:
        await update.effective_message.reply_text("لا توجد نتائج محفوظة بعد.")
        return
    await update.effective_message.reply_text(
        "🏆 لوحة المتصدرين\n" + "\n".join(
            f"{i}. {r['name']} — {r['points']} نقطة | {r['correct']}/{r['answered']} صحيحة"
            for i, r in enumerate(rows, 1)
        )
    )

def start_health_server() -> None:
    port = int(os.getenv("PORT", "10000"))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/health"):
                self.send_response(404)
                self.end_headers()
                return
            body = b'{"status":"ok","service":"telegram-quiz-bot"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_args):
            return
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")
    init_db()
    start_health_server()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler(["end", "stop"], end_quiz))
    app.add_handler(CommandHandler("cancel", cancel_quiz))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))
    app.add_handler(CallbackQueryHandler(answer, pattern=r"^ans:"))
    log.info("Starting Telegram quiz bot polling")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
