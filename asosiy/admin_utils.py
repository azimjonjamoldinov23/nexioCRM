from django.contrib import admin


FIELD_LABELS_UZ = {
    "name": "Nomi",
    "subject": "Fan / yo‘nalish",
    "teacher": "O‘qituvchi",
    "monthly_price": "Oylik to‘lov",
    "start_date": "Boshlanish sanasi",
    "end_date": "Tugash sanasi",
    "lesson_days": "Dars kunlari",
    "lesson_time": "Dars vaqti",
    "room": "Xona",
    "is_active": "Faol",
    "is_staff": "Xodimlar paneliga kira oladi",
    "is_superuser": "Barcha ruxsatlarga ega",
    "user": "Foydalanuvchi",
    "groups": "Guruhlar",
    "user_permissions": "Foydalanuvchi ruxsatlari",
    "last_login": "Oxirgi kirish vaqti",
    "date_joined": "Ro‘yxatdan o‘tgan vaqt",
    "password1": "Parol",
    "password2": "Parolni tasdiqlang",
    "birth_date": "Tug‘ilgan sana",
    "parent_name": "Ota-ona F.I.Sh",
    "parent_phone": "Ota-ona telefon raqami",
    "address": "Manzil",
    "note": "Izoh",
    "created_at": "Yaratilgan vaqt",
    "student": "O‘quvchi",
    "group": "Guruh",
    "discount_percent": "Chegirma foizi",
    "status": "Holati",
    "date": "Sana",
    "topic": "Dars mavzusi",
    "is_held": "Dars o‘tildi",
    "cancel_reason": "Bekor qilish sababi",
    "created_by": "Yaratgan foydalanuvchi",
    "lesson": "Dars",
    "comment": "Izoh",
    "marked_by": "Davomatni belgilagan",
    "marked_at": "Belgilangan vaqt",
    "enrollment": "Guruh a’zoligi",
    "amount": "To‘lov summasi",
    "period": "To‘lov davri",
    "paid_at": "To‘langan sana",
    "method": "To‘lov usuli",
    "receipt_no": "Kvitansiya raqami",
    "full_name": "F.I.Sh",
    "phone": "Telefon raqami",
    "course": "Kurs",
    "telegram_id": "Telegram ID",
    "telegram_username": "Telegram foydalanuvchi nomi",
    "username": "Foydalanuvchi nomi",
    "password": "Parol",
    "first_name": "Ism",
    "last_name": "Familiya",
    "email": "Elektron pochta",
    "phone_number": "Telefon raqami",
    "rasm": "Profil rasmi",
}


class UzbekLabelsMixin:
    change_list_template = "admin/crm_change_list.html"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        label = FIELD_LABELS_UZ.get(db_field.name)
        if formfield and label:
            formfield.label = label
        return formfield


class UzbekModelAdmin(UzbekLabelsMixin, admin.ModelAdmin):
    pass


class UzbekTabularInline(UzbekLabelsMixin, admin.TabularInline):
    pass
