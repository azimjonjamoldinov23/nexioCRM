import os
import re
from asgiref.sync import sync_to_async
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from asosiy.models import Ariza, Group, Student
from foydalanuvchilar.models import User

COURSE, NAME, SURNAME, PHONE, CONFIRM = range(5)

DEFAULT_COURSES = [
    "💻 Dasturlash",
    "🇬🇧 Ingliz tili",
    "📐 Matematika",
    "🎨 Grafik dizayn",
    "🤖 Robototexnika",
    "📊 SMM & Marketing",
]


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Ro'yxatdan o'tish")]],
        resize_keyboard=True,
    )


def phone_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📱 Raqamni yuborish", request_contact=True)],
            [KeyboardButton("❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


@sync_to_async
def get_available_courses() -> list[str]:
    db_subjects = list(
        Group.objects.filter(is_active=True)
        .values_list('subject', flat=True)
        .distinct()
    )
    result = []
    for sub in db_subjects:
        if sub and sub.strip():
            result.append(f"📚 {sub.strip()}")

    for d in DEFAULT_COURSES:
        clean_name = re.sub(r'^[^\w\s]+', '', d).strip().lower()
        if not any(clean_name in r.lower() for r in result):
            result.append(d)

    return result


async def get_courses_inline_keyboard() -> InlineKeyboardMarkup:
    courses = await get_available_courses()
    buttons = []
    row = []
    for idx, c in enumerate(courses):
        row.append(InlineKeyboardButton(c, callback_data=f"reg_course:{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


@sync_to_async
def save_registration(
    first_name: str,
    last_name: str,
    phone: str,
    course: str,
    telegram_id: int,
    telegram_username: str,
) -> Ariza:
    full_name = f"{first_name} {last_name}".strip()

    # 1. Ariza (Lead) saqlash
    ariza = Ariza.objects.create(
        full_name=full_name,
        phone=phone,
        course=course,
        telegram_id=telegram_id,
        telegram_username=telegram_username or '',
    )

    # 2. Foydalanuvchini (User) nexio.CRM da qidirish yoki yaratish
    user = User.objects.filter(telegram_id=telegram_id).first()
    if not user:
        user = User.objects.filter(phone=phone).first()

    if user:
        user.full_name = full_name
        user.phone = phone
        user.telegram_id = telegram_id
        if user.role != User.Role.ADMIN and user.role != User.Role.TEACHER:
            user.role = User.Role.STUDENT
        user.save()
    else:
        username = telegram_username or f"user_{telegram_id}"
        if User.objects.filter(username=username).exists():
            username = f"user_{telegram_id}"
            if User.objects.filter(username=username).exists():
                username = f"u_{phone.replace('+', '')}"

        user = User.objects.create(
            username=username,
            full_name=full_name,
            phone=phone,
            role=User.Role.STUDENT,
            telegram_id=telegram_id,
            is_active=True,
        )
        user.set_unusable_password()
        user.save()

    # 3. Student profili yaratish
    Student.objects.get_or_create(
        user=user,
        defaults={
            'note': f"nexio.CRM orqali ro'yxatdan o'tdi. Tanlangan kurs: {course}",
        },
    )

    return ariza


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = await get_courses_inline_keyboard()
    courses = await get_available_courses()
    context.user_data['available_courses'] = courses

    text = "Kurslarimizdan birini tanlang:"
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)

    return COURSE


async def course_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    courses = context.user_data.get('available_courses')
    if not courses:
        courses = await get_available_courses()
        context.user_data['available_courses'] = courses

    idx_str = query.data.replace("reg_course:", "")
    try:
        idx = int(idx_str)
        course_name = courses[idx]
    except (ValueError, IndexError):
        course_name = "💻 Dasturlash"

    context.user_data['reg_course'] = course_name

    # Rasmdagi kabi "Tanlangan kurs: 💻 Dasturlash" ga o'zgaradi
    await query.edit_message_text(f"Tanlangan kurs: {course_name}")

    # Keyingi xabar: "Ismingizni kiriting:"
    await query.message.reply_text("Ismingizni kiriting:")
    return NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip().capitalize()
    if len(name) < 2:
        await update.message.reply_text("Iltimos, ismingizni to'g'ri kiriting:")
        return NAME

    context.user_data['reg_first_name'] = name
    await update.message.reply_text("Familiyangizni kiriting:")
    return SURNAME


async def surname_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    surname = update.message.text.strip().capitalize()
    if len(surname) < 2:
        await update.message.reply_text("Iltimos, familiyangizni to'g'ri kiriting:")
        return SURNAME

    context.user_data['reg_last_name'] = surname

    text = (
        "Telefon raqamingizni yuboring.\n"
        "Pastdagi tugmani bosing yoki qo'lda yozing: +998901234567"
    )
    await update.message.reply_text(text, reply_markup=phone_reply_keyboard())
    return PHONE


def normalize_uzbek_phone(phone_text: str) -> str | None:
    digits = re.sub(r'\D', '', phone_text)
    if digits.startswith('998') and len(digits) == 12:
        return f"+{digits}"
    elif len(digits) == 9:
        return f"+998{digits}"
    elif phone_text.startswith('+998') and len(digits) == 12:
        return f"+{digits}"
    return None


async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.contact
    if contact and contact.phone_number:
        phone = contact.phone_number
        if not phone.startswith('+'):
            phone = f"+{phone}"
    else:
        raw_text = update.message.text.strip()
        phone = normalize_uzbek_phone(raw_text)
        if not phone:
            await update.message.reply_text(
                "Iltimos, telefon raqamingizni to'g'ri formatda yuboring: +998901234567 yoki pastdagi tugmani bosing.",
                reply_markup=phone_reply_keyboard(),
            )
            return PHONE

    context.user_data['reg_phone'] = phone

    course = context.user_data.get('reg_course', 'Noma\'lum')
    first_name = context.user_data.get('reg_first_name', '')
    last_name = context.user_data.get('reg_last_name', '')

    text = (
        "Ma'lumotlaringiz qabul qilindi ✅\n\n"
        "Ma'lumotlarni tekshiring:\n\n"
        f"👨‍💻 Kurs: {course}\n"
        f"👤 Ism: {first_name}\n"
        f"👥 Familiya: {last_name}\n"
        f"📞 Telefon: {phone}"
    )

    confirm_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="reg_confirm"),
            InlineKeyboardButton("🔄 Qaytadan", callback_data="reg_retry"),
        ]
    ])

    await update.message.reply_text(
        text,
        reply_markup=confirm_keyboard,
    )
    return CONFIRM


async def confirm_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    course = context.user_data.get('reg_course', '')
    first_name = context.user_data.get('reg_first_name', '')
    last_name = context.user_data.get('reg_last_name', '')
    phone = context.user_data.get('reg_phone', '')
    full_name = f"{first_name} {last_name}".strip()
    user = query.from_user

    # nexio.CRM ma'lumotlar bazasiga saqlash (Ariza, User, Student)
    await save_registration(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        course=course,
        telegram_id=user.id,
        telegram_username=user.username or '',
    )

    # nexio.CRM administratoriga xabar yuborish
    admin_id = os.getenv('ADMIN_TELEGRAM_ID', '').strip()
    if admin_id:
        try:
            admin_text = (
                "📥 nexio.CRM: Yangi o'quvchi ro'yxatdan o'tdi!\n\n"
                f"👨‍💻 Kurs: {course}\n"
                f"👤 F.I.Sh: {full_name}\n"
                f"📞 Telefon: {phone}\n"
                f"💬 Telegram: @{user.username or 'yoq'} (ID: {user.id})"
            )
            await context.bot.send_message(chat_id=int(admin_id), text=admin_text)
        except Exception as e:
            print(f"nexio.CRM adminga xabarnoma yuborishda xatolik: {e}")

    # Foydalanuvchiga muvaffaqiyat xabari (rasmdagi 4-skrinshot)
    success_text = "🎉 Arizangiz qabul qilindi! Tez orada administratorimiz siz bilan bog'lanadi."
    await query.message.reply_text(
        success_text,
        reply_markup=main_reply_keyboard(),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def retry_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = await get_courses_inline_keyboard()
    courses = await get_available_courses()
    context.user_data['available_courses'] = courses
    await query.message.reply_text("Kurslarimizdan birini tanlang:", reply_markup=keyboard)
    return COURSE


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    msg = "Ro'yxatdan o'tish bekor qilindi."
    if update.message:
        await update.message.reply_text(msg, reply_markup=main_reply_keyboard())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg)
        await update.callback_query.message.reply_text(
            "Kurslarimizga ro'yxatdan o'tish uchun pastdagi tugmani bosing.",
            reply_markup=main_reply_keyboard(),
        )

    return ConversationHandler.END


registration_conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^Ro'yxatdan o'tish$"), start_registration),
        CommandHandler("register", start_registration),
    ],
    states={
        COURSE: [
            CallbackQueryHandler(course_selected, pattern=r"^reg_course:"),
        ],
        NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^❌ Bekor qilish$"), name_received),
        ],
        SURNAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^❌ Bekor qilish$"), surname_received),
        ],
        PHONE: [
            MessageHandler(filters.CONTACT, phone_received),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^❌ Bekor qilish$"), phone_received),
        ],
        CONFIRM: [
            CallbackQueryHandler(confirm_received, pattern=r"^reg_confirm$"),
            CallbackQueryHandler(retry_registration, pattern=r"^reg_retry$"),
        ],
    },
    fallbacks=[
        MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_registration),
        CommandHandler("cancel", cancel_registration),
        CallbackQueryHandler(cancel_registration, pattern=r"^reg_cancel$"),
    ],
    allow_reentry=True,
    per_message=False,
)

