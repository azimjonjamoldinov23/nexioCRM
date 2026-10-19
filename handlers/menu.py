import os
from datetime import date
from django.db.models import Sum
from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from asosiy.models import Ariza, Enrollment, Group, Payment, Student
from foydalanuvchilar.models import User


@sync_to_async
def get_role(telegram_id: int) -> str | None:
    admin_id = os.getenv('ADMIN_TELEGRAM_ID', '').strip()
    if admin_id and str(telegram_id) == admin_id:
        return User.Role.ADMIN

    return User.objects.filter(telegram_id=telegram_id, is_active=True).values_list(
        'role', flat=True
    ).first()


@sync_to_async
def get_new_arizalar_count() -> int:
    return Ariza.objects.filter(status=Ariza.Status.YANGI).count()


async def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    new_count = await get_new_arizalar_count()
    ariza_btn = f"📥 Yangi arizalar ({new_count})" if new_count > 0 else "📥 Arizalar ro'yxati"

    buttons = [
        [InlineKeyboardButton(ariza_btn, callback_data='admin_arizalar')],
        [
            InlineKeyboardButton("📊 CRM statistikasi", callback_data='admin_stats'),
            InlineKeyboardButton("💰 To'lovlar", callback_data='admin_payments'),
        ],
        [
            InlineKeyboardButton("👥 Guruhlar ro'yxati", callback_data='admin_groups'),
            InlineKeyboardButton("⚙️ Guruh boshqaruvi", callback_data='manage_groups'),
        ],
        [InlineKeyboardButton("🎓 O'quvchilar ro'yxati", callback_data='admin_students')],
        [InlineKeyboardButton("🔄 Yangilash", callback_data='refresh_menu')],
    ]
    return InlineKeyboardMarkup(buttons)


def student_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📚 Mening guruhlarim", callback_data='student_groups')],
        [InlineKeyboardButton("💳 Mening to'lovlarim", callback_data='student_payments')],
        [InlineKeyboardButton("🔄 Qayta tekshirish", callback_data='refresh_menu')],
    ]
    return InlineKeyboardMarkup(buttons)


async def keyboard_for_role(role: str | None) -> InlineKeyboardMarkup:
    if role == User.Role.ADMIN:
        return await get_admin_menu_keyboard()
    elif role == User.Role.STUDENT:
        return student_menu_keyboard()
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Qayta tekshirish", callback_data='refresh_menu')],
        ])


@sync_to_async
def get_admin_stats() -> str:
    total_students = User.objects.filter(role=User.Role.STUDENT).count()
    active_students = Student.objects.filter(enrollments__status=Enrollment.Status.ACTIVE).distinct().count()
    total_groups = Group.objects.count()
    active_groups = Group.objects.filter(is_active=True).count()
    new_arizalar = Ariza.objects.filter(status=Ariza.Status.YANGI).count()
    total_arizalar = Ariza.objects.count()
    total_payments_count = Payment.objects.count()
    payments_sum = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
    formatted_sum = f"{payments_sum:,.0f} so'm".replace(',', ' ')

    return (
        "📊 <b>nexio.CRM Boshqaruv Statistikasi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎓 <b>O'quvchilar:</b>\n"
        f"  • Faol o'quvchilar: <b>{active_students} nafar</b>\n"
        f"  • Bazadagi jami o'quvchilar: <b>{total_students} nafar</b>\n\n"
        "📚 <b>Guruhlar:</b>\n"
        f"  • Faol guruhlar: <b>{active_groups} ta</b>\n"
        f"  • Jami guruhlar: <b>{total_groups} ta</b>\n\n"
        "📥 <b>Arizalar (Lidlar):</b>\n"
        f"  • 🟡 Yangi (ko'rilmagan): <b>{new_arizalar} ta</b>\n"
        f"  • 📋 Jami kelib tushgan: <b>{total_arizalar} ta</b>\n\n"
        "💰 <b>Moliya (To'lovlar):</b>\n"
        f"  • Jami to'lovlar soni: <b>{total_payments_count} ta</b>\n"
        f"  • Jami tushum: <b>{formatted_sum}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )


@sync_to_async
def get_arizalar_list() -> tuple[str, list[tuple[int, str, str]]]:
    arizalar = list(Ariza.objects.all().order_by('-created_at')[:8])
    if not arizalar:
        return "📥 <b>Arizalar bo'limi:</b>\n\nHozircha arizalar mavjud emas. Yangi ro'yxatdan o'tganlar shu yerda ko'rinadi.", []

    status_map = {
        'yangi': '🟡 Yangi',
        'boglanildi': '📞 Bog\'lanildi',
        'qabul_qilindi': '🟢 Qabul qilindi',
        'bekor_qilindi': '🔴 Bekor qilindi',
    }

    lines = ["📥 <b>Kelib tushgan arizalar:</b>\n<i>Tafsilotini ko'rish uchun quyidagi tugmalardan birini bosing:</i>\n"]
    items = []
    for idx, a in enumerate(arizalar, 1):
        st_txt = status_map.get(a.status, a.status)
        date_str = a.created_at.strftime('%d.%m %H:%M')
        lines.append(f"{idx}. 👤 <b>{a.full_name}</b> ({a.course})\n   📞 {a.phone} | {st_txt} | 📅 {date_str}")
        btn_label = f"{'🟡' if a.status == 'yangi' else '⚪'} {a.full_name[:18]}"
        items.append((a.id, btn_label, a.status))

    return "\n".join(lines), items


def arizalar_keyboard(items: list[tuple[int, str, str]]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for ariza_id, label, _ in items:
        row.append(InlineKeyboardButton(label, callback_data=f"admin_ariza_detail:{ariza_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 Asosiy menyu", callback_data='back_menu')])
    return InlineKeyboardMarkup(buttons)


@sync_to_async
def get_ariza_detail(ariza_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    try:
        a = Ariza.objects.get(id=ariza_id)
    except Ariza.DoesNotExist:
        return "Ariza topilmadi.", None

    status_map = {
        'yangi': '🟡 Yangi',
        'boglanildi': '📞 Bog\'lanildi',
        'qabul_qilindi': '🟢 Qabul qilindi',
        'bekor_qilindi': '🔴 Bekor qilindi',
    }
    date_str = a.created_at.strftime('%d.%m.%Y %H:%M')
    tg_username = f"@{a.telegram_username}" if a.telegram_username else "kiritilmagan"
    tg_id_str = str(a.telegram_id) if a.telegram_id else "yoq"

    text = (
        f"📄 <b>Ariza #{a.id} tafsilotlari:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>F.I.Sh:</b> {a.full_name}\n"
        f"📚 <b>Kurs:</b> {a.course}\n"
        f"📞 <b>Telefon:</b> {a.phone}\n"
        f"💬 <b>Telegram:</b> {tg_username} (ID: <code>{tg_id_str}</code>)\n"
        f"📌 <b>Holati:</b> <b>{status_map.get(a.status, a.status)}</b>\n"
        f"📅 <b>Yuborilgan vaqt:</b> {date_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Holatni o'zgartirish uchun quyidagi tugmalardan birini bosing:</i>"
    )

    buttons = [
        [
            InlineKeyboardButton("📞 Bog'lanildi", callback_data=f"ariza_status:{a.id}:boglanildi"),
            InlineKeyboardButton("🟢 Qabul qilindi", callback_data=f"ariza_status:{a.id}:qabul_qilindi"),
        ],
        [
            InlineKeyboardButton("🔴 Bekor qilish", callback_data=f"ariza_status:{a.id}:bekor_qilindi"),
        ],
        [
            InlineKeyboardButton("🔙 Arizalar ro'yxatiga", callback_data="admin_arizalar"),
            InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back_menu"),
        ],
    ]
    return text, InlineKeyboardMarkup(buttons)


@sync_to_async
def change_ariza_status(ariza_id: int, new_status: str) -> str:
    try:
        a = Ariza.objects.get(id=ariza_id)
        a.status = new_status
        a.save()
        return "Muvaffaqiyatli saqlandi! ✅"
    except Ariza.DoesNotExist:
        return "Ariza topilmadi!"


def group_icon(subject: str) -> str:
    icons = {
        'Matematika': '🔢',
        'Fizika': '⚛️',
        'Ingliz tili': '🇬🇧',
        'Dasturlash': '💻',
        'Grafik dizayn': '🎨',
        'Robototexnika': '🤖',
        'SMM va marketing': '📣',
    }
    return icons.get(subject, '📚')


@sync_to_async
def get_admin_groups_text() -> str:
    groups = Group.objects.select_related('teacher').order_by('name')
    if not groups:
        return "📚 <b>Guruhlar:</b>\nHozircha guruhlar mavjud emas."

    lines = ["📚 <b>nexio.CRM Barcha Guruhlar Ro'yxati:</b>\n"]
    for idx, g in enumerate(groups, 1):
        teacher_name = g.teacher.full_name if g.teacher else "Biriktirilmagan"
        count = g.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
        price_fmt = f"{g.monthly_price:,.0f} so'm".replace(',', ' ')
        time_str = g.lesson_time.strftime('%H:%M') if g.lesson_time else ""
        status = "✅ Faol" if g.is_active else "⏸️ Faol emas"
        lines.append(
            f"{idx}. {group_icon(g.subject)} <b>{g.name}</b> ({g.subject}) — {status}\n"
            f"   👨‍🏫 O'qituvchi: {teacher_name}\n"
            f"   👥 O'quvchilar: <b>{count} nafar</b>\n"
            f"   💰 Narxi: <b>{price_fmt}</b>/oy | ⏰ {g.lesson_days} {time_str}"
        )

    return "\n\n".join(lines)


@sync_to_async
def get_admin_payments_text() -> str:
    payments = Payment.objects.select_related('enrollment__student__user', 'enrollment__group').order_by('-paid_at')[:10]
    if not payments:
        return "💰 <b>To'lovlar:</b>\n\nHozircha to'lovlar mavjud emas."

    method_icons = {'cash': '💵 Naqd', 'card': '💳 Karta', 'transfer': '🏦 O\'tkazma'}
    lines = ["💰 <b>nexio.CRM Oxirgi 10 ta To'lov:</b>\n"]
    for idx, p in enumerate(payments, 1):
        name = p.enrollment.student.user.full_name
        grp = p.enrollment.group.name
        amt = f"{p.amount:,.0f} so'm".replace(',', ' ')
        m_txt = method_icons.get(p.method, p.method)
        date_str = p.paid_at.strftime('%d.%m.%Y') if hasattr(p.paid_at, 'strftime') else str(p.paid_at)
        lines.append(f"{idx}. 👤 <b>{name}</b> ({grp})\n   {m_txt}: <b>{amt}</b> | 📅 {date_str}")

    return "\n\n".join(lines)


@sync_to_async
def get_admin_students() -> str:
    students = User.objects.filter(
        role=User.Role.STUDENT,
        is_active=True,
    ).prefetch_related('student_profile__enrollments__group').order_by('-id')[:15]
    if not students:
        return "🎓 <b>O'quvchilar:</b>\nHozircha o'quvchilar mavjud emas."

    lines = ["🎓 <b>nexio.CRM O'quvchilar Ro'yxati:</b>\n"]
    for idx, user in enumerate(students, 1):
        phone_txt = user.phone or 'yo\'q'
        tg_txt = f"@{user.username}" if user.username else (f"ID: {user.telegram_id}" if user.telegram_id else "yo'q")
        groups = []
        if hasattr(user, 'student_profile') and user.student_profile:
            groups = list(user.student_profile.enrollments.filter(
                status=Enrollment.Status.ACTIVE,
            ).values_list('group__name', flat=True))
        grp_txt = f"📚 {', '.join(groups)}" if groups else "⚪ Guruhsiz"
        lines.append(f"{idx}. 👤 <b>{user.full_name}</b>\n   📞 {phone_txt} | 💬 {tg_txt}\n   {grp_txt}")

    return "\n\n".join(lines)


@sync_to_async
def get_manage_groups() -> list[tuple[int, str, str]]:
    return list(Group.objects.order_by('name').values_list('id', 'name', 'subject'))


def manage_groups_keyboard(groups: list[tuple[int, str, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(f"{group_icon(subject)} {name}", callback_data=f'admin_group:{group_id}')]
        for group_id, name, subject in groups
    ]
    buttons.append([InlineKeyboardButton("🔙 Asosiy menyu", callback_data='back_menu')])
    return InlineKeyboardMarkup(buttons)


@sync_to_async
def get_group_students(group_id: int) -> tuple[str, list[tuple[int, str]]]:
    group = Group.objects.get(id=group_id)
    students = list(
        Enrollment.objects.filter(
            group_id=group_id,
            status=Enrollment.Status.ACTIVE,
        ).select_related('student__user').values_list(
            'student_id', 'student__user__full_name'
        )
    )
    if students:
        text = f"📘 <b>{group.name}</b> guruhi ({group.subject}):\n\n👥 <b>Guruhdagi faol o'quvchilar:</b>\n" + '\n'.join(
            f"{i}. 👤 {name}" for i, (_, name) in enumerate(students, 1)
        )
    else:
        text = f"📘 <b>{group.name}</b> guruhida hozircha faol o'quvchilar mavjud emas."
    return text, []


@sync_to_async
def get_students_to_add(group_id: int) -> tuple[str, list[tuple[int, str]]]:
    group = Group.objects.get(id=group_id)
    enrolled_ids = Enrollment.objects.filter(group_id=group_id).values_list(
        'student_id', flat=True
    )
    students = list(
        User.objects.filter(
            role=User.Role.STUDENT,
            is_active=True,
            student_profile__isnull=False,
        ).exclude(student_profile__id__in=enrolled_ids).values_list(
            'student_profile__id', 'full_name'
        )
    )
    return f"➕ <b>{group.name}</b> guruhiga qo'shish uchun o'quvchini tanlang:", students


def add_students_keyboard(group_id: int, students: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(f"👤 {name}", callback_data=f'admin_enroll:{group_id}:{student_id}')]
        for student_id, name in students
    ]
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data=f'admin_group:{group_id}')])
    return InlineKeyboardMarkup(buttons)


@sync_to_async
def enroll_student(group_id: int, student_id: int) -> str:
    group = Group.objects.get(id=group_id)
    student = User.objects.get(student_profile__id=student_id)
    Enrollment.objects.get_or_create(
        student_id=student_id,
        group_id=group_id,
        start_date=date.today(),
        defaults={'status': Enrollment.Status.ACTIVE, 'discount_percent': 0},
    )
    return f"✅ <b>{student.full_name}</b> {group.name} guruhiga muvaffaqiyatli qo'shildi!"


@sync_to_async
def get_student_groups(telegram_id: int) -> str:
    student_id = User.objects.filter(telegram_id=telegram_id).values_list(
        'student_profile__id', flat=True
    ).first()
    if not student_id:
        return "Siz hali CRMga o'quvchi sifatida biriktirilmagansiz."

    enrollments = Enrollment.objects.filter(
        student_id=student_id,
        status=Enrollment.Status.ACTIVE,
    ).select_related('group')
    if not enrollments:
        return "Sizda hozircha faol guruhlar mavjud emas."

    return "📚 <b>Mening guruhlarim:</b>\n" + '\n'.join(
        f"• 📘 <b>{item.group.name}</b> ({item.group.subject})" for item in enrollments
    )


@sync_to_async
def get_student_payments(telegram_id: int) -> str:
    student_id = User.objects.filter(telegram_id=telegram_id).values_list(
        'student_profile__id', flat=True
    ).first()
    if not student_id:
        return "Siz hali CRMga o'quvchi sifatida biriktirilmagansiz."

    payments = Payment.objects.filter(
        enrollment__student_id=student_id,
    ).order_by('-paid_at')[:10]
    if not payments:
        return "Siz uchun to'lovlar topilmadi."

    return "💳 <b>Mening oxirgi to'lovlarim:</b>\n" + '\n'.join(
        f"• <b>{payment.amount:,.0f} so'm</b> | 📅 {payment.paid_at}".replace(',', ' ') for payment in payments
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.data and query.data.startswith('reg_'):
        return

    telegram_id = query.from_user.id
    role = await get_role(telegram_id)

    # 1. Asosiy menyuga qaytish yoki yangilash
    if query.data in ['back_menu', 'refresh_menu']:
        await query.answer("Menyu yangilandi 🔄")
        if role == User.Role.ADMIN:
            await query.edit_message_text(
                "👨‍💼 <b>nexio.CRM — Markaziy Admin Boshqaruv Paneli:</b>\n\nKerakli bo'limni tanlang:",
                parse_mode='HTML',
                reply_markup=await get_admin_menu_keyboard(),
            )
        else:
            await query.edit_message_text(
                "Kerakli bo'limni tanlang:",
                reply_markup=await keyboard_for_role(role),
            )
        return

    # 2. Arizalar ro'yxati
    if query.data == 'admin_arizalar' and role == User.Role.ADMIN:
        await query.answer()
        text, items = await get_arizalar_list()
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=arizalar_keyboard(items),
        )
        return

    # 3. Ariza tafsiloti
    if query.data.startswith('admin_ariza_detail:') and role == User.Role.ADMIN:
        await query.answer()
        ariza_id = int(query.data.split(':')[1])
        text, kb = await get_ariza_detail(ariza_id)
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=kb,
        )
        return

    # 4. Ariza holatini o'zgartirish
    if query.data.startswith('ariza_status:') and role == User.Role.ADMIN:
        _, ariza_id_str, new_st = query.data.split(':')
        ariza_id = int(ariza_id_str)
        res_msg = await change_ariza_status(ariza_id, new_st)
        await query.answer(res_msg)
        text, kb = await get_ariza_detail(ariza_id)
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=kb,
        )
        return

    # 5. CRM statistikasi
    if query.data == 'admin_stats' and role == User.Role.ADMIN:
        await query.answer()
        text = await get_admin_stats()
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👥 Guruhlar ro'yxati", callback_data='admin_groups'),
                    InlineKeyboardButton("⚙️ Guruh boshqaruvi", callback_data='manage_groups'),
                ],
                [
                    InlineKeyboardButton("🔄 Yangilash", callback_data='admin_stats'),
                    InlineKeyboardButton("🔙 Asosiy menyu", callback_data='back_menu'),
                ],
            ]),
        )
        return

    # 6. To'lovlar ro'yxati
    if query.data == 'admin_payments' and role == User.Role.ADMIN:
        await query.answer()
        text = await get_admin_payments_text()
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Asosiy menyu", callback_data='back_menu')],
            ]),
        )
        return

    # 7. Guruhlar ro'yxati
    if query.data == 'admin_groups' and role == User.Role.ADMIN:
        await query.answer()
        text = await get_admin_groups_text()
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚙️ Guruhlarni boshqarish", callback_data='manage_groups'),
                    InlineKeyboardButton("🔙 Asosiy menyu", callback_data='back_menu'),
                ],
            ]),
        )
        return

    # 8. Guruhlarni boshqarish
    if query.data == 'manage_groups' and role == User.Role.ADMIN:
        await query.answer()
        groups = await get_manage_groups()
        await query.edit_message_text(
            "⚙️ <b>Guruhlarni boshqarish:</b>\n\nBoshqarish uchun guruhni tanlang:",
            parse_mode='HTML',
            reply_markup=manage_groups_keyboard(groups),
        )
        return

    # 9. Guruh ichidagi o'quvchilar
    if query.data.startswith('admin_group:') and role == User.Role.ADMIN:
        await query.answer()
        group_id = int(query.data.split(':')[1])
        text, _ = await get_group_students(group_id)
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ O'quvchi qo'shish", callback_data=f'admin_add_student:{group_id}')],
                [
                    InlineKeyboardButton("🔙 Guruhlar ro'yxati", callback_data='manage_groups'),
                    InlineKeyboardButton("🏠 Asosiy menyu", callback_data='back_menu'),
                ],
            ]),
        )
        return

    # 10. O'quvchi qo'shish ro'yxati
    if query.data.startswith('admin_add_student:') and role == User.Role.ADMIN:
        await query.answer()
        group_id = int(query.data.split(':')[1])
        text, students = await get_students_to_add(group_id)
        if not students:
            text = "Bu guruhga qo'shish uchun bo'sh o'quvchi topilmadi."
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=add_students_keyboard(group_id, students),
        )
        return

    # 11. O'quvchini guruhga kiritish
    if query.data.startswith('admin_enroll:') and role == User.Role.ADMIN:
        _, group_id, student_id = query.data.split(':')
        text = await enroll_student(int(group_id), int(student_id))
        await query.answer("O'quvchi guruhga qo'shildi! ✅")
        group_text, _ = await get_group_students(int(group_id))
        await query.edit_message_text(
            f"{text}\n\n{group_text}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Yana o'quvchi qo'shish", callback_data=f'admin_add_student:{group_id}')],
                [InlineKeyboardButton("🔙 Guruhlar", callback_data='manage_groups')],
            ]),
        )
        return

    # 12. O'quvchilar ro'yxati
    if query.data == 'admin_students' and role == User.Role.ADMIN:
        await query.answer()
        text = await get_admin_students()
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚙️ Guruhlarni boshqarish", callback_data='manage_groups'),
                    InlineKeyboardButton("🔙 Asosiy menyu", callback_data='back_menu'),
                ],
            ]),
        )
        return

    # Student menyusi amallari
    if query.data == 'student_groups' and role == User.Role.STUDENT:
        await query.answer()
        text = await get_student_groups(telegram_id)
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data='back_menu')],
            ]),
        )
        return
    elif query.data == 'student_payments' and role == User.Role.STUDENT:
        await query.answer()
        text = await get_student_payments(telegram_id)
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data='back_menu')],
            ]),
        )
        return

    await query.answer("Bu amal sizning rolingiz uchun mavjud emas.")
