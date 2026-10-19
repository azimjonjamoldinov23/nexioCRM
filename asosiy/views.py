from types import SimpleNamespace

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    AdminGroupForm,
    AdminLessonForm,
    AdminPaymentForm,
    AdminTeacherForm,
    AdminStudentForm,
    AdminEnrollmentForm,
)
from .models import Ariza, Enrollment, Group, Payment, Student, Lesson, Attendance
from foydalanuvchilar.models import User


def crm_admin_required(view_func):
    """
    Ruxsat tekshiruvi: is_staff, is_superuser yoki role='admin' bo'lgan foydalanuvchilarni kiritadi.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('admin_login')}?next={request.path}")
        user = request.user
        if user.is_staff or user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Sizda admin panelga kirish huquqi yo‘q.")
        return redirect("index")
    return _wrapped_view


# ============================================================
# STUDENT PROFILINI OLISH / YARATISH
# ============================================================

def get_or_create_student_profile(user):
    """
    Foydalanuvchi uchun Student profilini olish yoki yaratish.
    """

    if (
        user.role != User.Role.STUDENT
        and not user.is_staff
        and not user.is_superuser
    ):
        user.role = User.Role.STUDENT
        user.save(update_fields=["role"])

    student, _ = Student.objects.get_or_create(user=user)

    return student


# ============================================================
# BUGUNGI KUNNI GURUH JADVALI BILAN TEKSHIRISH
# ============================================================

def group_has_lesson_today(group, today):
    """
    Guruhning lesson_days maydonida bugungi kun borligini tekshiradi.

    Misollar:
        Mon Wed Fri
        Tue Thu Sat
        Du/Cho/Ju
        Se/Pay/Sh
    """

    lesson_days = getattr(group, "lesson_days", "") or ""

    lesson_days = str(lesson_days).strip()

    if not lesson_days:
        return False

    # Har xil yozilishlarni bir xil ko'rinishga keltiramiz
    normalized = (
        lesson_days
        .replace(",", " ")
        .replace("/", " ")
        .replace("-", " ")
        .replace(".", " ")
        .lower()
    )

    # Bugungi hafta kuni
    weekday = today.weekday()

    # Python:
    # 0 = Dushanba
    # 1 = Seshanba
    # 2 = Chorshanba
    # 3 = Payshanba
    # 4 = Juma
    # 5 = Shanba
    # 6 = Yakshanba

    day_variants = {
        0: ["mon", "du", "dushanba"],
        1: ["tue", "tu", "se", "seshanba"],
        2: ["wed", "we", "cho", "ch", "chorshanba"],
        3: ["thu", "th", "pay", "p", "payshanba"],
        4: ["fri", "fr", "ju", "juma"],
        5: ["sat", "sa", "sh", "shanba"],
        6: ["sun", "su", "ya", "yakshanba"],
    }

    variants = day_variants.get(weekday, [])

    for variant in variants:
        if variant in normalized.split():
            return True

    # Masalan eski formatlar:
    # Du/Cho/Ju
    # Se/Pay/Sh
    compact = (
        lesson_days
        .lower()
        .replace(" ", "")
        .replace("-", "/")
        .replace(".", "/")
    )

    compact_variants = {
        0: ["du", "dushanba"],
        1: ["se", "seshanba"],
        2: ["cho", "ch", "chorshanba"],
        3: ["pay", "p", "payshanba"],
        4: ["ju", "juma"],
        5: ["sh", "shanba"],
        6: ["ya", "yakshanba"],
    }

    for variant in compact_variants.get(weekday, []):
        if variant in compact:
            return True

    return False


# ============================================================
# DASHBOARD
# ============================================================

@crm_admin_required
def admin_panel(request):
    dashboard_stats = {
        "students_count": Student.objects.count(),
        "active_groups_count": Group.objects.filter(is_active=True).count(),
        "new_arizalar_count": Ariza.objects.filter(
            status=Ariza.Status.YANGI
        ).count(),
        "payments_sum": Payment.objects.aggregate(total=Sum("amount"))["total"] or 0,
    }
    return render(
        request,
        "asosiy/admin.html",
        {"page": "dashboard", "dashboard_stats": dashboard_stats},
    )


@crm_admin_required
def admin_groups(request):
    groups = Group.objects.select_related("teacher").annotate(
        active_students_count=Count(
            "enrollments",
            filter=Q(enrollments__status=Enrollment.Status.ACTIVE),
            distinct=True,
        )
    )
    query = request.GET.get("q", "").strip()
    if query:
        groups = groups.filter(
            Q(name__icontains=query)
            | Q(subject__icontains=query)
            | Q(teacher__full_name__icontains=query)
        )

    return render(
        request,
        "asosiy/admin.html",
        {
            "page": "groups",
            "groups": groups,
            "groups_count": groups.count(),
            "query": query,
        },
    )


@crm_admin_required
def admin_group_create(request):
    form = AdminGroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Yangi guruh yaratildi.")
        return redirect("admin_groups")

    return render(
        request,
        "asosiy/admin.html",
        {"page": "group_form", "form": form, "form_title": "Yangi guruh ochish"},
    )


@crm_admin_required
def admin_group_edit(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    form = AdminGroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guruh ma’lumotlari saqlandi.")
        return redirect("admin_groups")

    return render(
        request,
        "asosiy/admin.html",
        {
            "page": "group_form",
            "form": form,
            "form_title": f"{group.name} guruhini boshqarish",
            "group": group,
        },
    )


@crm_admin_required
def admin_group_students(request, group_id):
    group = get_object_or_404(
        Group.objects.select_related("teacher"),
        pk=group_id,
    )
    enrollments = Enrollment.objects.filter(group=group).select_related(
        "student__user"
    ).annotate(total_paid=Sum("payments__amount")).order_by(
        "status", "student__user__full_name"
    )
    query = request.GET.get("q", "").strip()
    if query:
        enrollments = enrollments.filter(
            Q(student__user__full_name__icontains=query)
            | Q(student__user__phone__icontains=query)
            | Q(student__user__username__icontains=query)
        )

    return render(
        request,
        "asosiy/admin.html",
        {
            "page": "group_students",
            "group": group,
            "enrollments": enrollments,
            "students_count": enrollments.count(),
            "active_students_count": enrollments.filter(
                status=Enrollment.Status.ACTIVE
            ).count(),
            "query": query,
        },
    )


@crm_admin_required
@require_POST
def admin_group_delete(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if group.enrollments.exists():
        group.is_active = False
        group.save(update_fields=["is_active"])
        messages.warning(
            request,
            f"“{group.name}” guruhida o‘quvchilar tarixi borligi uchun o‘chirilmay, arxivlandi.",
        )
    else:
        group.delete()
        messages.success(request, "Guruh o‘chirildi.")
    return redirect("admin_groups")


@crm_admin_required
def admin_teachers(request):
    teachers = User.objects.filter(
        role=User.Role.TEACHER,
        is_active=True,
    ).annotate(
        active_groups_count=Count(
            "teaching_groups",
            filter=Q(teaching_groups__is_active=True),
            distinct=True,
        )
    ).order_by("full_name")
    return render(
        request,
        "asosiy/admin.html",
        {"page": "teachers", "teachers": teachers, "teachers_count": teachers.count()},
    )


@crm_admin_required
@require_http_methods(["GET", "POST"])
def admin_teacher_create(request):
    form = AdminTeacherForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "O‘qituvchi yaratildi.")
        return redirect("admin_teachers")

    return render(
        request,
        "asosiy/admin.html",
        {"page": "teacher_form", "form": form, "form_title": "Yangi o‘qituvchi qo‘shish"},
    )


@crm_admin_required
@require_POST
def admin_teacher_delete(request, teacher_id):
    teacher = get_object_or_404(
        User,
        pk=teacher_id,
        role=User.Role.TEACHER,
        is_staff=False,
        is_superuser=False,
    )
    has_history = (
        teacher.teaching_groups.exists()
        or teacher.created_lessons.exists()
        or teacher.marked_attendances.exists()
        or teacher.created_payments.exists()
    )
    if has_history:
        teacher.is_active = False
        teacher.save(update_fields=["is_active"])
        messages.warning(
            request,
            f"“{teacher.full_name}” tarixiy yozuvlarga bog‘langan. Hisob o‘chirilmadi, nofaol qilindi.",
        )
    else:
        teacher.delete()
        messages.success(request, "O‘qituvchi o‘chirildi.")
    return redirect("admin_teachers")


@crm_admin_required
@require_http_methods(["GET", "POST"])
def admin_lesson_create(request):
    form = AdminLessonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        lesson = form.save(commit=False)
        lesson.created_by = request.user
        lesson.save()
        messages.success(request, "Dars jadvalga qo‘shildi.")
        return redirect(f"{reverse('admin_attendance')}?lesson={lesson.pk}")

    return render(
        request,
        "asosiy/admin.html",
        {"page": "lesson_form", "form": form, "form_title": "Yangi dars qo‘shish"},
    )


@crm_admin_required
@require_http_methods(["GET", "POST"])
def admin_payments(request):
    payments = Payment.objects.select_related(
        "enrollment__student__user", "enrollment__group", "created_by"
    ).order_by("-paid_at", "-created_at")
    return render(
        request,
        "asosiy/admin.html",
        {
            "page": "payments",
            "payments": payments,
            "payments_sum": payments.aggregate(total=Sum("amount"))["total"] or 0,
        },
    )


@crm_admin_required
@require_http_methods(["GET", "POST"])
def admin_payment_create(request):
    form = AdminPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        payment = form.save(commit=False)
        payment.created_by = request.user
        payment.save()
        messages.success(request, "To‘lov muvaffaqiyatli qayd etildi.")
        return redirect("admin_payments")

    return render(
        request,
        "asosiy/admin.html",
        {"page": "payment_form", "form": form, "form_title": "Yangi to‘lov qayd etish"},
    )


@crm_admin_required
@require_http_methods(["GET", "POST"])
def admin_attendance(request):
    groups = Group.objects.filter(is_active=True).select_related("teacher").annotate(
        active_students_count=Count(
            "enrollments",
            filter=Q(enrollments__status=Enrollment.Status.ACTIVE),
            distinct=True,
        )
    ).order_by("name")
    lesson_id = request.POST.get("lesson_id") if request.method == "POST" else request.GET.get("lesson")
    group_id = request.POST.get("group_id") if request.method == "POST" else request.GET.get("group")
    lesson = None
    selected_group = None
    lesson_date = timezone.localdate()
    students = []
    form_error = ""

    if lesson_id:
        lesson = get_object_or_404(
            Lesson.objects.select_related("group"),
            pk=lesson_id,
        )
        selected_group = lesson.group
        lesson_date = lesson.date
    elif group_id:
        selected_group = get_object_or_404(Group, pk=group_id, is_active=True)
        requested_date = request.POST.get("lesson_date") if request.method == "POST" else request.GET.get("date")
        if requested_date:
            parsed_date = parse_date(requested_date)
            if parsed_date is None:
                form_error = "Dars sanasini to‘g‘ri kiriting."
            else:
                lesson_date = parsed_date

    if selected_group and not form_error:
        if lesson is None:
            lesson = Lesson.objects.filter(
                group=selected_group,
                date=lesson_date,
            ).first()
        enrollments = Enrollment.objects.filter(
            group=selected_group,
            status=Enrollment.Status.ACTIVE,
            start_date__lte=lesson_date,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=lesson_date)
        ).select_related("student", "student__user")
        students = [enrollment.student for enrollment in enrollments]
        existing_attendance = {
            entry.student_id: entry
            for entry in Attendance.objects.filter(lesson=lesson, student__in=students)
        } if lesson else {}
        for student in students:
            student.lesson_attendance = existing_attendance.get(student.pk)
            student.attendance_status = (
                request.POST.get(f"status_{student.pk}")
                if request.method == "POST"
                else getattr(student.lesson_attendance, "status", Attendance.Status.PRESENT)
            )

        if request.method == "POST":
            valid_statuses = {value for value, _label in Attendance.Status.choices}
            invalid_status = any(
                student.attendance_status not in valid_statuses
                for student in students
            )
            if invalid_status:
                form_error = "Har bir o‘quvchi uchun davomat holatini tanlang."
            elif not students:
                form_error = "Tanlangan sana uchun faol o‘quvchilar topilmadi."
            elif lesson and not lesson.is_held:
                form_error = "Bekor qilingan darsga davomat yozib bo‘lmaydi."
            else:
                with transaction.atomic():
                    lesson, _ = Lesson.objects.get_or_create(
                        group=selected_group,
                        date=lesson_date,
                        defaults={
                            "topic": "Davomat",
                            "created_by": request.user,
                        },
                    )
                    for student in students:
                        Attendance.objects.update_or_create(
                            lesson=lesson,
                            student=student,
                            defaults={
                                "status": student.attendance_status,
                                "marked_by": request.user,
                            },
                        )
                messages.success(request, "Davomat muvaffaqiyatli saqlandi.")
                return redirect(
                    f"{reverse('admin_attendance')}?group={selected_group.pk}&date={lesson_date.isoformat()}"
                )

    return render(
        request,
        "asosiy/admin.html",
        {
            "page": "attendance",
            "groups": groups,
            "selected_group": selected_group,
            "lesson_date": lesson_date,
            "lesson": lesson,
            "students": students,
            "attendance_statuses": Attendance.Status.choices,
            "form_error": form_error,
        },
    )


@crm_admin_required
def admin_students(request):
    students = Student.objects.select_related("user").annotate(
        active_groups_count=Count(
            "enrollments",
            filter=Q(enrollments__status=Enrollment.Status.ACTIVE),
            distinct=True,
        )
    )
    query = request.GET.get("q", "").strip()
    if query:
        students = students.filter(
            Q(user__full_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__phone__icontains=query)
            | Q(user__email__icontains=query)
        )

    return render(
        request,
        "asosiy/admin.html",
        {
            "page": "students",
            "students": students,
            "students_count": students.count(),
            "query": query,
        },
    )


@crm_admin_required
def admin_student_create(request):
    form = AdminStudentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"O‘quvchi '{user.full_name}' muvaffaqiyatli qo‘shildi.")
        return redirect("admin_students")

    return render(
        request,
        "asosiy/admin.html",
        {"page": "student_form", "form": form, "form_title": "Yangi o‘quvchi qo‘shish"},
    )


@crm_admin_required
def admin_student_enroll(request, student_id):
    student = get_object_or_404(Student.objects.select_related("user"), pk=student_id)
    form = AdminEnrollmentForm(
        request.POST or None,
        initial={"student": student, "start_date": timezone.localdate()}
    )
    if request.method == "POST" and form.is_valid():
        enrollment = form.save()
        messages.success(request, f"'{student.user.full_name}' muvaffaqiyatli '{enrollment.group.name}' guruhiga biriktirildi.")
        return redirect("admin_students")

    return render(
        request,
        "asosiy/admin.html",
        {"page": "enroll_form", "form": form, "form_title": f"Guruhga biriktirish: {student.user.full_name}", "student": student},
    )


@crm_admin_required
@require_POST
def admin_student_delete(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    user = student.user
    if student.enrollments.exists() or student.attendances.exists():
        user.is_active = False
        user.save(update_fields=["is_active"])
        messages.warning(request, f"'{user.full_name}' o‘quv tarixi mavjudligi sababli nofaol qilindi.")
    else:
        user.delete()
        messages.success(request, "O‘quvchi o‘chirildi.")
    return redirect("admin_students")


@crm_admin_required
@require_POST
def admin_payment_delete(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    try:
        payment.delete()
        messages.success(request, "To‘lov yozuvi o‘chirildi.")
    except Exception as e:
        messages.error(request, f"To‘lovni o‘chirib bo‘lmadi: {e}")
    return redirect("admin_payments")


@crm_admin_required
def admin_arizalar(request):
    status_filter = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    arizalar = Ariza.objects.all().order_by("-created_at")

    if status_filter:
        arizalar = arizalar.filter(status=status_filter)
    if query:
        arizalar = arizalar.filter(
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(course__icontains=query)
            | Q(telegram_username__icontains=query)
        )

    stats = {
        "yangi": Ariza.objects.filter(status=Ariza.Status.YANGI).count(),
        "boglanildi": Ariza.objects.filter(status=Ariza.Status.BOGLANILDI).count(),
        "qabul": Ariza.objects.filter(status=Ariza.Status.QABUL_QILINDI).count(),
        "bekor": Ariza.objects.filter(status=Ariza.Status.BEKOR_QILINDI).count(),
        "jami": Ariza.objects.count(),
    }

    return render(
        request,
        "asosiy/admin.html",
        {
            "page": "arizalar",
            "arizalar": arizalar,
            "stats": stats,
            "status_filter": status_filter,
            "query": query,
            "statuses": Ariza.Status.choices,
        },
    )


@crm_admin_required
@require_POST
def admin_ariza_status(request, ariza_id, new_status):
    ariza = get_object_or_404(Ariza, pk=ariza_id)
    valid_statuses = dict(Ariza.Status.choices)
    if new_status in valid_statuses:
        ariza.status = new_status
        ariza.save(update_fields=["status"])
        messages.success(request, f"Ariza holati '{valid_statuses[new_status]}' ga o‘zgartirildi.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_arizalar")


@crm_admin_required
@require_POST
def admin_ariza_delete(request, ariza_id):
    ariza = get_object_or_404(Ariza, pk=ariza_id)
    ariza.delete()
    messages.success(request, "Ariza muvaffaqiyatli o‘chirildi.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_arizalar")


@login_required
def index(request):
    user = request.user
    student = getattr(user, "student_profile", None)

    my_groups_count = 0
    enrolled_groups = []
    today_lessons = []

    if student:
        # O'quvchi a'zo bo'lgan faol guruhlar
        enrolled_groups = list(
            Group.objects.filter(
                enrollments__student=student,
                enrollments__status=Enrollment.Status.ACTIVE,
                is_active=True,
            )
            .select_related("teacher")
            .distinct()
        )

        my_groups_count = len(enrolled_groups)

        # Bugungi sana
        today = timezone.localdate()

        # Bugun bo'ladigan darslar
        # DIQQAT: Lesson modelida start_time yo'q,
        # shuning uchun faqat date bo'yicha saralanadi.
        today_lessons = list(
            Lesson.objects.filter(
                group__in=enrolled_groups,
                date=today,
            )
            .select_related("group", "group__teacher")
            .order_by("date", "id")
        )

        # Har bir dars uchun o'quvchining davomatini topamiz
        lesson_ids = [lesson.id for lesson in today_lessons]

        attendances = Attendance.objects.filter(
            student=student,
            lesson_id__in=lesson_ids,
        )

        attendance_map = {
            attendance.lesson_id: attendance
            for attendance in attendances
        }

        for lesson in today_lessons:
            lesson.user_attendance = attendance_map.get(lesson.id)

    context = {
        "my_groups_count": my_groups_count,
        "my_groups": enrolled_groups,
        "today_lessons": today_lessons,
    }

    return render(
        request,
        "asosiy/index.html",
        context
    )
@login_required
def guruhlarim(request):

    student = get_or_create_student_profile(request.user)

    # Foydalanuvchi a'zo bo'lgan faol guruhlar
    enrolled_enrollments = (
        Enrollment.objects.filter(
            student=student,
            status=Enrollment.Status.ACTIVE
        )
        
        .select_related(
            "group",
            "group__teacher"
        )
    )

    enrolled_group_ids = set(
        enrolled_enrollments.values_list(
            "group_id",
            flat=True
        )
    )

    my_groups = [
        enrollment.group
        for enrollment in enrolled_enrollments
    ]

    # Barcha faol guruhlar
    all_groups = list(
        Group.objects.filter(
            is_active=True
        )
        .select_related("teacher")
    )

    # A'zolik holatini belgilash
    for group in all_groups:
        group.is_enrolled = (
            group.id in enrolled_group_ids
        )

    context = {
        "student": student,
        "my_groups": my_groups,
        "all_groups": all_groups,
        "enrolled_count": len(my_groups),
        "total_count": len(all_groups),
    }

    return render(
        request,
        "asosiy/guruhlarim.html",
        context
    )


# ============================================================
# GURUHGA YOZILISH
# ============================================================

@login_required
def guruhga_yozilish(request, group_id):

    group = get_object_or_404(
        Group,
        id=group_id
    )

    student = get_or_create_student_profile(
        request.user
    )

    # Oldindan a'zo ekanligini tekshirish
    existing_enrollment = (
        Enrollment.objects.filter(
            student=student,
            group=group,
            status=Enrollment.Status.ACTIVE
        )
        .first()
    )

    if request.method == "POST":

        if existing_enrollment:

            messages.info(
                request,
                f"Siz allaqachon '{group.name}' guruhiga a'zo bo'lgansiz."
            )

            return redirect("guruhlarim")

        today = timezone.localdate()

        enrollment, created = (
            Enrollment.objects.get_or_create(
                student=student,
                group=group,
                defaults={
                    "start_date": today,
                    "status": Enrollment.Status.ACTIVE,
                }
            )
        )

        if not created:

            enrollment.status = (
                Enrollment.Status.ACTIVE
            )

            enrollment.start_date = today

            enrollment.save(
                update_fields=[
                    "status",
                    "start_date"
                ]
            )

        messages.success(
            request,
            f"Tabriklaymiz! Siz '{group.name}' guruhiga muvaffaqiyatli yozildingiz."
        )

        return redirect("guruhlarim")

    context = {
        "group": group,
        "student": student,
        "is_enrolled": bool(
            existing_enrollment
        ),
    }

    return render(
        request,
        "asosiy/guruhga_yozilish.html",
        context
    )


# ============================================================
# GURUHDAN CHIQISH
# ============================================================

@login_required
def guruhdan_chiqish(request, group_id):

    group = get_object_or_404(
        Group,
        id=group_id
    )

    student = get_or_create_student_profile(
        request.user
    )

    enrollment = (
        Enrollment.objects.filter(
            student=student,
            group=group,
            status=Enrollment.Status.ACTIVE
        )
        .first()
    )

    if enrollment:

        enrollment.status = (
            Enrollment.Status.DROPPED
        )

        enrollment.end_date = (
            timezone.localdate()
        )

        enrollment.save(
            update_fields=[
                "status",
                "end_date"
            ]
        )

        messages.warning(
            request,
            f"Siz '{group.name}' guruhidan chiqdingiz."
        )

    return redirect("guruhlarim")


# ============================================================
# MENING DARSLARIM
# ============================================================

@login_required
def darslarim(request):

    student = get_or_create_student_profile(
        request.user
    )

    # Talabaning faol guruhlari
    enrolled_enrollments = (
        Enrollment.objects.filter(
            student=student,
            status=Enrollment.Status.ACTIVE
        )
        .select_related(
            "group",
            "group__teacher"
        )
    )

    my_groups = [
        enrollment.group
        for enrollment in enrolled_enrollments
    ]

    my_group_ids = [
        group.id
        for group in my_groups
    ]

    # Ushbu guruhlarning barcha darslari
    lessons = list(
        Lesson.objects.filter(
            group_id__in=my_group_ids
        )
        .select_related(
            "group",
            "group__teacher"
        )
        .order_by(
            "-date"
        )
    )

    # Talabaning davomatlari
    lesson_ids = [
        lesson.id
        for lesson in lessons
    ]

    attendances = Attendance.objects.filter(
        student=student,
        lesson_id__in=lesson_ids
    )

    att_map = {
        attendance.lesson_id: attendance
        for attendance in attendances
    }

    for lesson in lessons:

        lesson.user_attendance = (
            att_map.get(lesson.id)
        )

    today = timezone.localdate()

    context = {
        "student": student,
        "my_groups": my_groups,
        "lessons": lessons,
        "groups_count": len(my_groups),
        "total_lessons_count": len(lessons),
        "today": today,
    }

    return render(
        request,
        "asosiy/darslarim.html",
        context
    )