import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ---------------- إعدادات البوت ----------------
TOKEN = os.environ.get("8169559283:AAGRln4XS6jUyT0J4qjJqUTN4Nvy8m0_Axc")

SUPERVISORS_GROUP_ID = -1003576246959
FINAL_CHANNEL_ID = -1003494248444

# ---------------- كلمات ممنوعة ----------------
BANNED_WORDS = [
    "كلبة", "حيوانة", "بقرة", "جموسة", "قحبة",
    "كلب", "منيوك", "معرص", "عرص", "قحبه",
    "كس ام", "كس", "كسم", "شرموطة", "حيوان",
    "مبعوص", "بعص", "باعص", "اخو", "معيرص"
]

# ---------------- تسجيل اللوج ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- تخزين البيانات ----------------
user_data = {}
pending_messages = {}

# ---------------- دوال مساعدة ----------------
def contains_banned_words(text: str) -> bool:
    if not text:
        return False
    text = text.lower()
    return any(word in text for word in BANNED_WORDS)

# ---------------- /start ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("👨 طالب", callback_data="set_gender:طالب"),
        InlineKeyboardButton("👩 طالبة", callback_data="set_gender:طالبة")
    ]]
    await update.message.reply_text(
        "👋 أهلاً بيك\n\nاختار نوعك:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- الأزرار ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("set_gender:"):
        gender = query.data.split(":")[1]
        user_id = query.from_user.id
        user_data[user_id] = {"gender": gender, "messages_count": 0}
        await query.edit_message_text(f"✅ تم تسجيلك كـ {gender}")

    elif query.data.startswith(("approve:", "reject:")):
        action, user_id, msg_id = query.data.split(":")
        user_id = int(user_id)
        msg_id = int(msg_id)

        original_message = pending_messages.get((user_id, msg_id))
        if not original_message:
            await query.edit_message_text("❌ الرسالة غير موجودة")
            return

        gender = user_data.get(user_id, {}).get("gender", "طالب")
        prefix = f"📨 رسالة مُحوّلة من {gender}\n\n"

        try:
            if action == "approve":
                if original_message["text"]:
                    await context.bot.send_message(
                        FINAL_CHANNEL_ID,
                        prefix + original_message["text"]
                    )
                elif original_message["photo"]:
                    await context.bot.send_photo(
                        FINAL_CHANNEL_ID,
                        original_message["photo"],
                        caption=prefix + (original_message.get("caption") or "")
                    )
                elif original_message["document"]:
                    await context.bot.send_document(
                        FINAL_CHANNEL_ID,
                        original_message["document"],
                        caption=prefix + (original_message.get("caption") or "")
                    )

                await query.edit_message_text("✅ تمت الموافقة ونشر الرسالة في القناة")

            else:
                await query.edit_message_text("❌ تم رفض الرسالة")

            pending_messages.pop((user_id, msg_id), None)

        except Exception as e:
            logger.error(e)
            await query.edit_message_text("❌ حصل خطأ أثناء التنفيذ")

# ---------------- استقبال رسائل الخاص ----------------
async def forward_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    user_id = user.id

    if user_id not in user_data:
        await message.reply_text("⚠️ من فضلك استخدم /start الأول")
        return

    text = message.text or message.caption or ""
    if contains_banned_words(text):
        await message.reply_text("❌ رسالتك مرفوضة بسبب ألفاظ غير مناسبة")
        return

    user_data[user_id]["messages_count"] += 1
    gender = user_data[user_id]["gender"]
    count = user_data[user_id]["messages_count"]

    pending_messages[(user_id, message.message_id)] = {
        "text": message.text,
        "photo": message.photo[-1].file_id if message.photo else None,
        "document": message.document.file_id if message.document else None,
        "caption": message.caption
    }

    keyboard = [[
        InlineKeyboardButton("✅ موافقة", callback_data=f"approve:{user_id}:{message.message_id}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"reject:{user_id}:{message.message_id}")
    ]]

    header = (
        f"📨 رسالة مُحوّلة\n"
        f"👤 من: {gender}\n"
        f"🧮 عدد الرسائل: {count}\n\n"
    )

    if message.text:
        await context.bot.send_message(
            SUPERVISORS_GROUP_ID,
            header + message.text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif message.photo:
        await context.bot.send_photo(
            SUPERVISORS_GROUP_ID,
            message.photo[-1].file_id,
            caption=header + (message.caption or ""),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif message.document:
        await context.bot.send_document(
            SUPERVISORS_GROUP_ID,
            message.document.file_id,
            caption=header + (message.caption or ""),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    await message.reply_text("✅ تم إرسال رسالتك للمراجعة")

# ---------------- أخطاء ----------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(context.error)

# ---------------- main ----------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO | filters.Document.ALL),
            forward_to_group
        )
    )

    app.add_error_handler(error_handler)

    print("🤖 البوت شغال...")
    app.run_polling()

if __name__ == "__main__":
    main()
