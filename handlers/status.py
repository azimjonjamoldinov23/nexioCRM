from telegram import Update
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from asosiy.models import Ariza, Enrollment, Group, Student


@sync_to_async
def get_status_text() -> str:
    active_groups = Group.objects.filter(is_active=True).count()
    total_groups = Group.objects.count()
    total_students = Student.objects.count()
    active_enrolls = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).count()
    new_arizalar = Ariza.objects.filter(status=Ariza.Status.YANGI).count()

    return (
        "📊 <b>nexio.CRM Umumiy Holati:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📚 <b>Guruhlar:</b> {active_groups} ta faol (Jami: {total_groups})\n"
        f"🎓 <b>O'quvchilar:</b> {total_students} nafar\n"
        f"📋 <b>Faol a'zoliklar:</b> {active_enrolls} ta\n"
        f"📥 <b>Yangi ko'rilmagan arizalar:</b> {new_arizalar} ta\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = await get_status_text()
    await update.message.reply_text(message, parse_mode='HTML')
