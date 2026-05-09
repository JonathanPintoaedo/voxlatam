import os
import logging
import httpx
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

API_URL   = os.getenv("API_URL", "http://api:8000")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ── /start ────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎙 *VoxLatam — Transcripción y Doblaje con IA*\n\n"
        "Envíame un archivo de audio o video y te devuelvo:\n"
        "• 📄 Transcripción en texto + SRT\n"
        "• 🌎 Traducción al español\n"
        "• 🎬 Video con subtítulos quemados\n"
        "• 🗣 Video con doblaje de voz IA\n\n"
        "*Precios:*\n"
        "• Transcripción: $0.10 USD/min\n"
        "• Traducción + subtítulos: $0.18 USD/min\n"
        "• Doblaje completo: $0.50 USD/min\n"
        "• Plan Creator (20h/mes): $39 USD\n\n"
        "🎁 *Primeros 30 minutos GRATIS para nuevos usuarios*\n\n"
        "Mándame un archivo para empezar 👇",
        parse_mode="Markdown"
    )

# ── /creditos ─────────────────────────────────────────
async def cmd_credits(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/credits/{user_id}")
    credits = r.json().get("credits_usd", 0)
    await update.message.reply_text(
        f"💰 Tus créditos disponibles: *${credits:.2f} USD*",
        parse_mode="Markdown"
    )

# ── /jobs ─────────────────────────────────────────────
async def cmd_jobs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/jobs/user/{user_id}")
    jobs = r.json()
    if not jobs:
        await update.message.reply_text("No tienes trabajos aún. ¡Mándame un archivo!")
        return
    text = "📋 *Tus últimos trabajos:*\n\n"
    for j in jobs[:5]:
        status_emoji = {"completed": "✅", "failed": "❌", "queued": "⏳"}.get(j["status"], "🔄")
        text += f"{status_emoji} `{j['id'][:8]}...` — {j['mode']} — {j['status']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ── Recibir archivo ───────────────────────────────────
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    file_obj = msg.audio or msg.video or msg.document or msg.voice

    if not file_obj:
        await msg.reply_text("Por favor envía un archivo de audio o video (MP3, MP4, WAV, OGG, etc.)")
        return

    # Mostrar menú de opciones
    keyboard = [
        [InlineKeyboardButton("📄 Solo Transcripción — $0.10/min", callback_data="transcription")],
        [InlineKeyboardButton("🌎 Traducción + SRT — $0.18/min",   callback_data="translation")],
        [InlineKeyboardButton("🎬 Video con subtítulos — $0.18/min", callback_data="subtitles")],
        [InlineKeyboardButton("🗣 Doblaje completo — $0.50/min",    callback_data="dubbing")],
    ]
    ctx.user_data["pending_file_id"] = file_obj.file_id
    ctx.user_data["pending_file_name"] = getattr(file_obj, "file_name", "audio.ogg")

    await msg.reply_text(
        "¿Qué quieres hacer con este archivo?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── Procesar selección de modo ────────────────────────
async def handle_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    mode    = query.data
    user_id = str(query.from_user.id)
    file_id = ctx.user_data.get("pending_file_id")

    if not file_id:
        await query.message.reply_text("Por favor vuelve a enviar el archivo.")
        return

    await query.message.reply_text(
        "⏳ Descargando archivo y poniendo en cola...\n"
        "Te avisaré cuando esté listo ✅"
    )

    try:
        # Descargar archivo desde Telegram
        tg_file = await ctx.bot.get_file(file_id)
        file_name = ctx.user_data.get("pending_file_name", "input.mp4")
        local_path = f"/tmp/{user_id}_{file_name}"
        await tg_file.download_to_drive(local_path)

        # Enviar a la API
        async with httpx.AsyncClient(timeout=60) as client:
            with open(local_path, "rb") as f:
                r = await client.post(
                    f"{API_URL}/jobs/",
                    files={"file": (file_name, f)},
                    data={
                        "mode": mode,
                        "lang_source": "auto",
                        "lang_target": "es",
                        "telegram_user_id": user_id
                    }
                )

        job = r.json()
        ctx.user_data["last_job_id"] = job["job_id"]

        await query.message.reply_text(
            f"✅ Job creado: `{job['job_id'][:8]}...`\n"
            f"Modo: *{mode}*\n\n"
            f"Procesando... te aviso cuando esté listo 🎯",
            parse_mode="Markdown"
        )

    except Exception as e:
        log.error(f"Error procesando archivo: {e}")
        await query.message.reply_text(
            f"❌ Error al procesar el archivo: {str(e)[:200]}\n"
            "Por favor intenta de nuevo."
        )

# ── Main ──────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN no configurado en .env")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("creditos", cmd_credits))
    app.add_handler(CommandHandler("jobs",     cmd_jobs))
    app.add_handler(MessageHandler(
        filters.AUDIO | filters.VIDEO | filters.Document.ALL | filters.VOICE,
        handle_file
    ))
    app.add_handler(CallbackQueryHandler(handle_mode))

    log.info("🤖 Bot VoxLatam iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()
