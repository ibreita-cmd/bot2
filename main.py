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

# ============== إعدادات البوت ==============
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN غير موجود! تأكد من إضافته في متغيرات البيئة")

SUPERVISORS_GROUP_ID = -1003576246959
FINAL_CHANNEL_ID = -1003494248444

# ============== كلمات ممنوعة ==============
BANNED_WORDS = [
    "كلبة", "حيوانة", "بقرة", "جموسة", "قحبة",
    "كلب", "منيوك", "معرص", "عرص", "قحبه",
    "كس ام", "كس", "كسم", "شرموطة", "حيوان",
    "مبعوص", "بعص", "باعص", "اخو", "معيرص"
]

# ============== تسجيل اللوج ==============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============== تخزين البيانات ==============
user_data = {}
pending_messages = {}

# ============== دوال مساعدة ==============
def contains_banned_words(text: str) -> bool:
    """فحص النص للكلمات الممنوعة"""
    if not text:
        return False
    text = text.lower().strip()
    return any(word in text for word in BANNED_WORDS)

# ============== أمر /start ==============
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض خيارات اختيار النوع"""
    keyboard = [[
        InlineKeyboardButton("👨 طالب", callback_data="set_gender:طالب"),
        InlineKeyboardButton("👩 طالبة", callback_data="set_gender:طالبة")
    ]]
    await update.message.reply_text(
        "👋 أهلاً بيك في بوت الرسائل المجهولة\n\n"
        "📝 اختار نوعك عشان نقدر نستقبل رسائلك:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============== معالج الأزرار ==============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ضغطات الأزرار"""
    query = update.callback_query
    await query.answer()

    # تسجيل النوع
    if query.data.startswith("set_gender:"):
        gender = query.data.split(":")[1]
        user_id = query.from_user.id
        user_data[user_id] = {"gender": gender, "messages_count": 0}
        
        await query.edit_message_text(
            f"✅ تم تسجيلك كـ {gender}\n\n"
            "📨 الحين قدر ترسل رسائلك وراح يتم مراجعتها قبل النشر"
        )
        logger.info(f"User {user_id} registered as {gender}")

    # الموافقة أو الرفض
    elif query.data.startswith(("approve:", "reject:")):
        try:
            parts = query.data.split(":")
            action = parts[0]
            user_id = int(parts[1])
            msg_id = int(parts[2])
        except (ValueError, IndexError):
            await query.edit_message_text("❌ خطأ في البيانات")
            return

        # التحقق من وجود الرسالة
        original_message = pending_messages.get((user_id, msg_id))
        if not original_message:
            await query.edit_message_text("❌ الرسالة غير موجودة أو تم معالجتها مسبقاً")
            return

        gender = user_data.get(user_id, {}).get("gender", "مجهول")
        prefix = f"📨 رسالة من {gender}\n━━━━━━━━━━━━━━\n\n"

        try:
            if action == "approve":
                # نشر الرسالة في القناة
                if original_message["text"]:
                    await context.bot.send_message(
                        FINAL_CHANNEL_ID,
                        prefix + original_message["text"]
                    )
                elif original_message["photo"]:
                    caption = prefix + (original_message.get("caption") or "")
                    await context.bot.send_photo(
                        FINAL_CHANNEL_ID,
                        original_message["photo"],
                        caption=caption
                    )
                elif original_message["document"]:
                    caption = prefix + (original_message.get("caption") or "")
                    await context.bot.send_document(
                        FINAL_CHANNEL_ID,
                        original_message["document"],
                        caption=caption
                    )

                await query.edit_message_text("✅ تمت الموافقة ونشر الرسالة في القناة")
                logger.info(f"Message approved from user {user_id}")

                # إشعار المرسل
                try:
                    await context.bot.send_message(
                        user_id,
                        "✅ تم قبول رسالتك ونشرها في القناة!"
                    )
                except Exception:
                    pass

            else:  # reject
                await query.edit_message_text("❌ تم رفض الرسالة")
                logger.info(f"Message rejected from user {user_id}")
                
                # إشعار المرسل
                try:
                    await context.bot.send_message(
                        user_id,
                        "❌ للأسف تم رفض رسالتك من قبل الإدارة"
                    )
                except Exception:
                    pass

            # حذف الرسالة من القائمة المعلقة
            pending_messages.pop((user_id, msg_id), None)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await query.edit_message_text(f"❌ حصل خطأ أثناء التنفيذ:\n{str(e)}")

# ============== استقبال رسائل المستخدمين ==============
async def forward_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحويل الرسائل من المستخدمين إلى مجموعة المشرفين"""
    message = update.effective_message
    user = update.effective_user
    user_id = user.id

    # التحقق من تسجيل المستخدم
    if user_id not in user_data:
        await message.reply_text(
            "⚠️ من فضلك استخدم /start أولاً لاختيار نوعك"
        )
        return

    # فحص الكلمات الممنوعة
    text = message.text or message.caption or ""
    if contains_banned_words(text):
        await message.reply_text(
            "❌ رسالتك مرفوضة بسبب احتوائها على ألفاظ غير مناسبة\n\n"
            "⚠️ الرجاء إعادة صياغة الرسالة باحترام"
        )
        logger.warning(f"Banned words detected from user {user_id}")
        return

    # تحديث عداد الرسائل
    user_data[user_id]["messages_count"] += 1
    gender = user_data[user_id]["gender"]
    count = user_data[user_id]["messages_count"]

    # حفظ الرسالة للمراجعة
    pending_messages[(user_id, message.message_id)] = {
        "text": message.text,
        "photo": message.photo[-1].file_id if message.photo else None,
        "document": message.document.file_id if message.document else None,
        "caption": message.caption
    }

    # إنشاء أزرار الموافقة/الرفض
    keyboard = [[
        InlineKeyboardButton("✅ موافقة", callback_data=f"approve:{user_id}:{message.message_id}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"reject:{user_id}:{message.message_id}")
    ]]

    # رأس الرسالة للمشرفين
    header = (
        f"📨 رسالة جديدة للمراجعة\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 النوع: {gender}\n"
        f"🔢 ID: {user_id}\n"
        f"📊 عدد رسائله: {count}\n"
        f"━━━━━━━━━━━━━━\n\n"
    )

    try:
        # إرسال للمشرفين حسب نوع الرسالة
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

        await message.reply_text(
            "✅ تم إرسال رسالتك للمراجعة\n\n"
            "⏳ سيتم إشعارك عند قبولها أو رفضها"
        )
        logger.info(f"Message forwarded to supervisors from user {user_id}")

    except Exception as e:
        logger.error(f"Error forwarding message: {e}")
        await message.reply_text(
            "❌ حصل خطأ أثناء إرسال رسالتك\n"
            "الرجاء المحاولة مرة أخرى"
        )

# ============== معالج الأخطاء ==============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تسجيل الأخطاء"""
    logger.error(f"Exception while handling update: {context.error}")

# ============== البرنامج الرئيسي ==============
def main():
    """تشغيل البوت"""
    try:
        # إنشاء التطبيق
        app = Application.builder().token(TOKEN).build()

        # إضافة المعالجات
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(
            MessageHandler(
                filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO | filters.Document.ALL),
                forward_to_group
            )
        )
        app.add_error_handler(error_handler)

        # تشغيل البوت
        logger.info("🤖 البوت بدأ العمل...")
        print("🤖 البوت شغال بنجاح...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
