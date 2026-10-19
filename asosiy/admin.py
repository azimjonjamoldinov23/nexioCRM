from django.contrib import admin
from django.utils.html import format_html

from .models import Ariza, Attendance, Enrollment, Group, Lesson, Payment, Student
from django.db.models import Sum

from .admin_utils import UzbekModelAdmin, UzbekTabularInline

admin.site.site_header = "nexio.CRM Boshqaruv Paneli"
admin.site.site_title = "nexio.CRM Admin"
admin.site.index_title = "O'quv markazi monitoring va boshqaruvi"
admin.site.site_url = "/"

original_each_context = admin.site.each_context


def custom_each_context(request):
    context = original_each_context(request)
    try:
        payments_sum = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
        context['dashboard_stats'] = {
            'students_count': Student.objects.count(),
            'active_groups_count': Group.objects.filter(is_active=True).count(),
            'new_arizalar_count': Ariza.objects.filter(status=Ariza.Status.YANGI).count(),
            'payments_sum': f"{payments_sum:,.0f}".replace(',', ' '),
        }
    except Exception:
        pass
    return context


admin.site.each_context = custom_each_context



class EnrollmentInline(UzbekTabularInline):
    model = Enrollment
    extra = 1
    fields = ('student', 'group', 'start_date', 'status', 'discount_percent')
    autocomplete_fields = ()


class AttendanceInline(UzbekTabularInline):
    model = Attendance
    extra = 0
    fields = ('student', 'status', 'comment', 'marked_by')
    readonly_fields = ('marked_at',)


@admin.register(Group)
class GroupAdmin(UzbekModelAdmin):
    list_display = ('name', 'subject', 'teacher', 'formatted_price', 'student_count', 'lesson_days', 'lesson_time', 'is_active_badge')
    list_filter = ('subject', 'is_active', 'teacher', 'lesson_days')
    search_fields = ('name', 'subject', 'teacher__full_name')
    inlines = [EnrollmentInline]

    @admin.display(description="Oylik to'lov", ordering='monthly_price')
    def formatted_price(self, obj):
        return f"{obj.monthly_price:,.0f} so'm".replace(',', ' ')

    @admin.display(description="O'quvchilar soni")
    def student_count(self, obj):
        count = obj.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
        return format_html('<span style="font-weight: bold; color: #2563eb;">👥 {} nafar</span>', count)

    @admin.display(description="Holati", ordering='is_active')
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="background-color: #d1fae5; color: #065f46; padding: 4px 10px; border-radius: 12px; font-weight: 600;">Faol ✅</span>')
        return format_html('<span style="background-color: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 12px; font-weight: 600;">Nofaol ❌</span>')


@admin.register(Student)
class StudentAdmin(UzbekModelAdmin):
    list_display = ('full_name_display', 'phone_display', 'active_groups', 'parent_info', 'created_at')
    search_fields = ('user__full_name', 'user__phone', 'parent_name', 'parent_phone', 'user__username')
    list_filter = ('created_at',)
    inlines = [EnrollmentInline]

    @admin.display(description="O'quvchi F.I.Sh", ordering='user__full_name')
    def full_name_display(self, obj):
        return format_html('<b>👤 {}</b>', obj.user.full_name or obj.user.username)

    @admin.display(description="Telefon")
    def phone_display(self, obj):
        if obj.user.phone:
            return format_html('<a href="tel:{}" style="color: #2563eb; text-decoration: none;">📞 {}</a>', obj.user.phone, obj.user.phone)
        return "-"

    @admin.display(description="A'zo guruhlari")
    def active_groups(self, obj):
        groups = list(obj.enrollments.filter(status=Enrollment.Status.ACTIVE).values_list('group__name', flat=True))
        if groups:
            return format_html('<span style="color: #059669; font-weight: 600;">📚 {}</span>', ", ".join(groups))
        return format_html('<span style="color: #9ca3af;">Guruhsiz</span>')

    @admin.display(description="Ota-ona aloqasi")
    def parent_info(self, obj):
        if obj.parent_name or obj.parent_phone:
            return f"{obj.parent_name} ({obj.parent_phone})"
        return "-"


@admin.register(Enrollment)
class EnrollmentAdmin(UzbekModelAdmin):
    list_display = ('student', 'group', 'start_date', 'status_badge', 'discount_percent')
    list_filter = ('status', 'group', 'start_date')
    search_fields = ('student__user__full_name', 'group__name')

    @admin.display(description="A'zolik holati", ordering='status')
    def status_badge(self, obj):
        colors = {
            Enrollment.Status.ACTIVE: ('#d1fae5', '#065f46', 'Faol'),
            Enrollment.Status.PAUSED: ('#fef3c7', '#92400e', "To'xtatilgan"),
            Enrollment.Status.FINISHED: ('#e0e7ff', '#3730a3', 'Yakunlangan'),
            Enrollment.Status.DROPPED: ('#fee2e2', '#991b1b', 'Chiqqan'),
        }
        bg, fg, label = colors.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html('<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-weight: 600;">{}</span>', bg, fg, label)


@admin.register(Lesson)
class LessonAdmin(UzbekModelAdmin):
    list_display = ('group', 'date', 'topic', 'is_held_badge', 'created_by')
    list_filter = ('is_held', 'group', 'date')
    search_fields = ('topic', 'group__name')
    inlines = [AttendanceInline]

    @admin.display(description="Holati", ordering='is_held')
    def is_held_badge(self, obj):
        if obj.is_held:
            return format_html('<span style="background-color: #d1fae5; color: #065f46; padding: 4px 8px; border-radius: 10px;">O\'tildi ✅</span>')
        return format_html('<span style="background-color: #fee2e2; color: #991b1b; padding: 4px 8px; border-radius: 10px;">Bekor qilingan ❌</span>')


@admin.register(Attendance)
class AttendanceAdmin(UzbekModelAdmin):
    list_display = ('lesson', 'student', 'status_badge', 'marked_by', 'marked_at')
    list_filter = ('status', 'lesson__group', 'lesson__date')
    search_fields = ('student__user__full_name', 'lesson__topic', 'comment')

    @admin.display(description="Davomat", ordering='status')
    def status_badge(self, obj):
        colors = {
            Attendance.Status.PRESENT: ('#d1fae5', '#065f46', 'Keldi ✅'),
            Attendance.Status.ABSENT: ('#fee2e2', '#991b1b', 'Kelmadi ❌'),
            Attendance.Status.LATE: ('#fef3c7', '#92400e', 'Kechikdi ⏰'),
            Attendance.Status.EXCUSED: ('#e0e7ff', '#3730a3', 'Sababli 📋'),
        }
        bg, fg, label = colors.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html('<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-weight: 600;">{}</span>', bg, fg, label)


@admin.register(Payment)
class PaymentAdmin(UzbekModelAdmin):
    list_display = ('student_display', 'group_display', 'formatted_amount', 'paid_at', 'method_badge', 'receipt_no', 'created_by')
    list_filter = ('method', 'paid_at', 'period')
    search_fields = ('receipt_no', 'enrollment__student__user__full_name', 'enrollment__group__name')

    @admin.display(description="O'quvchi")
    def student_display(self, obj):
        return format_html('<b>👤 {}</b>', obj.enrollment.student.user.full_name)

    @admin.display(description="Guruh")
    def group_display(self, obj):
        return obj.enrollment.group.name

    @admin.display(description="To'lov summasi", ordering='amount')
    def formatted_amount(self, obj):
        return format_html('<span style="font-weight: 700; color: #059669;">💰 {}</span>', f"{obj.amount:,.0f} so'm".replace(',', ' '))

    @admin.display(description="Usuli", ordering='method')
    def method_badge(self, obj):
        icons = {
            Payment.Method.CASH: ('#d1fae5', '#065f46', '💵 Naqd'),
            Payment.Method.CARD: ('#dbeafe', '#1e40af', '💳 Karta'),
            Payment.Method.TRANSFER: ('#e0e7ff', '#3730a3', '🏦 O\'tkazma'),
        }
        bg, fg, label = icons.get(obj.method, ('#f3f4f6', '#374151', obj.method))
        return format_html('<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-weight: 600;">{}</span>', bg, fg, label)


@admin.register(Ariza)
class ArizaAdmin(UzbekModelAdmin):
    list_display = ('full_name_display', 'phone_link', 'course_badge', 'status_badge', 'telegram_display', 'created_at')
    list_filter = ('status', 'course', 'created_at')
    search_fields = ('full_name', 'phone', 'telegram_username', 'telegram_id')
    list_editable = ()
    actions = ['mark_as_contacted', 'mark_as_accepted', 'mark_as_cancelled']

    @admin.display(description="F.I.Sh", ordering='full_name')
    def full_name_display(self, obj):
        return format_html('<b>👤 {}</b>', obj.full_name)

    @admin.display(description="Telefon")
    def phone_link(self, obj):
        return format_html('<a href="tel:{}" style="color: #2563eb; text-decoration: none; font-weight: 600;">📞 {}</a>', obj.phone, obj.phone)

    @admin.display(description="Kurs", ordering='course')
    def course_badge(self, obj):
        return format_html('<span style="background-color: #f1f5f9; color: #0f172a; padding: 4px 8px; border-radius: 8px; font-weight: 600;">📚 {}</span>', obj.course)

    @admin.display(description="Holati", ordering='status')
    def status_badge(self, obj):
        colors = {
            Ariza.Status.YANGI: ('#dbeafe', '#1e40af', '🟡 Yangi'),
            Ariza.Status.BOGLANILDI: ('#fef3c7', '#92400e', '📞 Bog\'lanildi'),
            Ariza.Status.QABUL_QILINDI: ('#d1fae5', '#065f46', '🟢 Qabul qilindi'),
            Ariza.Status.BEKOR_QILINDI: ('#fee2e2', '#991b1b', '🔴 Bekor qilindi'),
        }
        bg, fg, label = colors.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html('<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-weight: 700;">{}</span>', bg, fg, label)

    @admin.display(description="Telegram")
    def telegram_display(self, obj):
        if obj.telegram_username:
            return format_html('<a href="https://t.me/{}" target="_blank" style="color: #0284c7; text-decoration: none;">💬 @{}</a>', obj.telegram_username, obj.telegram_username)
        elif obj.telegram_id:
            return format_html('<span style="color: #64748b;">ID: {}</span>', obj.telegram_id)
        return "-"

    @admin.action(description="Tanlangan arizalarni 'Bog'lanildi' deb belgilash")
    def mark_as_contacted(self, request, queryset):
        queryset.update(status=Ariza.Status.BOGLANILDI)
        self.message_user(request, "Tanlangan arizalar holati 'Bog'lanildi' ga o'zgartirildi.")

    @admin.action(description="Tanlangan arizalarni 'Qabul qilindi' deb belgilash")
    def mark_as_accepted(self, request, queryset):
        queryset.update(status=Ariza.Status.QABUL_QILINDI)
        self.message_user(request, "Tanlangan arizalar holati 'Qabul qilindi' ga o'zgartirildi.")

    @admin.action(description="Tanlangan arizalarni 'Bekor qilindi' deb belgilash")
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status=Ariza.Status.BEKOR_QILINDI)
        self.message_user(request, "Tanlangan arizalar bekor qilindi.")
