from telegram import Update
from telegram.ext import ContextTypes

from handlers.menu import get_role, keyboard_for_role
from handlers.registration import main_reply_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    full_name = (
        user.full_name
        or user.first_name
        or "Foydalanuvchi"
    )

    role = await get_role(user.id)

    # =========================
    # 👨‍💼 ADMIN
    # =========================
    if role == "admin":
        admin_text = (
            f"👨‍💼 <b>Assalomu alaykum, {full_name}!</b> 👋\n\n"
            
            f"🏢 <b>nexio.CRM — Administrator paneli</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            
            f"🔐 <b>Admin boshqaruv tizimiga xush kelibsiz!</b>\n\n"
            
            f"📊 O‘quv markazining asosiy jarayonlarini "
            f"shu yerdan boshqarishingiz mumkin.\n\n"
            
            f"👥 <b>O‘quvchilar</b>\n"
            f"👨‍🏫 <b>O‘qituvchilar</b>\n"
            f"📚 <b>Kurslar va guruhlar</b>\n"
            f"💰 <b>To‘lovlar</b>\n"
            f"📈 <b>Hisobotlar</b>\n"
            f"⚙️ <b>Tizim sozlamalari</b>\n\n"
            
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 <b>Kerakli bo‘limni tanlang:</b>"
        )

        await update.message.reply_text(
            admin_text,
            parse_mode="HTML",
            reply_markup=await keyboard_for_role(role),
        )

    # =========================
    # 🎓 STUDENT
    # =========================
    elif role == "student":
        student_text = (
            f"🎓 <b>Assalomu alaykum, {full_name}!</b> 👋\n\n"
            
            f"🏢 <b>nexio.CRM — O‘quvchi kabineti</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            
            f"📚 <b>O‘quv markazimiz tizimiga xush kelibsiz!</b>\n\n"
            
            f"Bu bo‘lim orqali o‘zingizga tegishli "
            f"ma’lumotlarni boshqarishingiz mumkin.\n\n"
            
            f"📖 Kurslarim\n"
            f"🗓 Dars jadvali\n"
            f"💰 To‘lovlarim\n"
            f"📊 Natijalarim\n"
            f"👤 Profilim\n\n"
            
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 <b>Kerakli bo‘limni tanlang:</b>"
        )

        await update.message.reply_text(
            student_text,
            parse_mode="HTML",
            reply_markup=await keyboard_for_role(role),
        )

    # =========================
    # 👤 RO‘YXATDAN O‘TMAGAN
    # =========================
    else:
        welcome_message = (
            f"👋 <b>Assalomu alaykum, {full_name}!</b>\n\n"
            
            f"🏢 <b>nexio.CRM</b>\n"
            f"🎓 O‘quv markazi boshqaruv tizimiga xush kelibsiz!\n\n"
            
            f"📚 Bizning kurslarimizdan foydalanish "
            f"uchun avval ro‘yxatdan o‘ting.\n\n"
            
            f"👇 <b>Ro‘yxatdan o‘tishni boshlash uchun "
            f"pastdagi tugmani bosing:</b>"
        )

        await update.message.reply_text(
            welcome_message,
            parse_mode="HTML",
            reply_markup=main_reply_keyboard(),
        )