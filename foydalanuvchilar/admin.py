from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from asosiy.admin_utils import FIELD_LABELS_UZ, UzbekLabelsMixin, UzbekModelAdmin

from .models import Direction, Profil, User


@admin.register(Direction)
class DirectionAdmin(UzbekModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield and db_field.name == "name":
            formfield.label = "Fan / yo‘nalish nomi"
        return formfield


@admin.register(Profil)
class ProfilAdmin(UzbekModelAdmin):
    list_display = ("user", "first_name", "last_name", "email", "phone_number")
    search_fields = ("user__username", "user__full_name", "email", "phone_number")


@admin.register(User)
class UserAdmin(UzbekLabelsMixin, BaseUserAdmin):
    list_display = ('username', 'full_name_display', 'role_badge', 'phone_display', 'telegram_display', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'full_name', 'phone', 'email', 'telegram_id')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Shaxsiy maʼlumot', {'fields': ('full_name', 'role', 'phone', 'telegram_id', 'email')}),
        ('Ruxsatlar', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Muhim sanalar', {'fields': ('last_login', 'date_joined', 'created_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'full_name', 'role', 'phone', 'email', 'password1', 'password2'),
        }),
    )
    readonly_fields = ('created_at', 'last_login', 'date_joined')

    @admin.display(description="F.I.Sh", ordering='full_name')
    def full_name_display(self, obj):
        return format_html('<b>{}</b>', obj.full_name or obj.username)

    @admin.display(description="Roli", ordering='role')
    def role_badge(self, obj):
        colors = {
            User.Role.ADMIN: ('#f3e8ff', '#6b21a8', '👑 Administrator'),
            User.Role.TEACHER: ('#e0f2fe', '#0369a1', '👨‍🏫 O\'qituvchi'),
            User.Role.STUDENT: ('#d1fae5', '#065f46', '🎓 O\'quvchi'),
        }
        bg, fg, label = colors.get(obj.role, ('#f3f4f6', '#374151', obj.role))
        return format_html('<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-weight: 600;">{}</span>', bg, fg, label)

    @admin.display(description="Telefon")
    def phone_display(self, obj):
        if obj.phone:
            return format_html('<a href="tel:{}" style="color: #2563eb; text-decoration: none;">📞 {}</a>', obj.phone, obj.phone)
        return "-"

    @admin.display(description="Telegram ID")
    def telegram_display(self, obj):
        if obj.telegram_id:
            return format_html('<span style="color: #0284c7; font-weight: 600;">🆔 {}</span>', obj.telegram_id)
        return format_html('<span style="color: #9ca3af;">yo\'q</span>')
