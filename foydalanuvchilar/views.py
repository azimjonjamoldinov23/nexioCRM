import re
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from .forms import AdminProfileForm, RegisterForm
from asosiy.views import crm_admin_required
from django.db.models import Count, Q, Sum
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import User, Profil
from django.contrib import messages
from telegram.error import TelegramError

from .telegram_integration import (
    TelegramIntegrationConfigError,
    notify_admin_new_registration,
)
from asosiy.models import Attendance, Payment, Student


User = get_user_model()
logger = logging.getLogger(__name__)


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser or getattr(request.user, "role", None) == User.Role.ADMIN:
            return redirect("admin_panel")
        return redirect("index")

    username_val = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        username_val = username

        # 1. To'g'ridan-to'g'ri username orqali authenticate qilish
        user = authenticate(
            request,
            username=username,
            password=password
        )

        # 2. Agar topilmasa, email orqali tekshirish
        if user is None and "@" in username:
            try:
                user_obj = User.objects.get(email__iexact=username)
                user = authenticate(request, username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass

        # 3. Agar topilmasa, telefon raqam orqali tekshirish
        if user is None and username:
            clean_phone = re.sub(r'[\s\-\(\)]', '', username)
            if not clean_phone.startswith("+"):
                if clean_phone.startswith("998"):
                    clean_phone = "+" + clean_phone
                elif len(clean_phone) == 9:
                    clean_phone = "+998" + clean_phone
            try:
                user_obj = User.objects.get(phone=clean_phone)
                user = authenticate(request, username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass

        if user is not None:
            login(request, user)
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url:
                return redirect(next_url)
            if user.is_staff or user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN:
                return redirect("admin_panel")
            return redirect("index")

        return render(request, "asosiy/login.html", {
            "error": "Foydalanuvchi nomi, email yoki parol noto‘g‘ri!",
            "username": username_val,
        })

    return render(request, "asosiy/login.html", {
        "username": username_val,
    })


def register(request):
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            try:
                notify_admin_new_registration(user)
            except (TelegramError, OSError, TelegramIntegrationConfigError):
                logger.exception(
                    "Telegram admin notification failed for website registration "
                    "of user %s.",
                    user.pk,
                )
            login(request, user)
            return redirect("index")

        return render(request, "asosiy/register.html", {
            "form": form
        })

    form = RegisterForm()
    return render(request, "asosiy/register.html", {
        "form": form
    })


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def davomatim(request):
    student, _ = Student.objects.get_or_create(user=request.user)
    davomatlar = Attendance.objects.filter(student=student).select_related(
        "lesson__group"
    ).order_by("-lesson__date", "-marked_at")
    stats = davomatlar.aggregate(
        jami=Count("id"),
        qatnashgan=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        kelmagan=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
        kechikkan=Count("id", filter=Q(status=Attendance.Status.LATE)),
    )
    return render(request, "asosiy/davomatim.html", {
        "davomatlar": davomatlar,
        "jami_darslar": stats["jami"],
        "qatnashgan": stats["qatnashgan"],
        "kelmagan": stats["kelmagan"],
        "kechikkan": stats["kechikkan"],
    })


@login_required
def reytinglarim(request):
    return render(request, "asosiy/reyting.html", {"reytinglar": []})


@login_required
def tolovlarim(request):
    student, _ = Student.objects.get_or_create(user=request.user)
    tolovlar = Payment.objects.filter(
        enrollment__student=student
    ).select_related("enrollment__group").order_by("-paid_at", "-created_at")
    stats = tolovlar.aggregate(jami=Sum("amount"), soni=Count("id"))
    return render(request, "asosiy/tolovlarim.html", {
        "tolovlar": tolovlar,
        "jami_tolov": stats["jami"] or 0,
        "muvaffaqiyatli_tolovlar": stats["soni"],
        "kutilayotgan_tolovlar": 0,
    })

def chat(request):
    return render(request, "asosiy/chat.html", {
    "chat": chat,
})


@login_required
def profil(request):
    user = request.user
    profile, created = Profil.objects.get_or_create(user=user)

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        username = request.POST.get("username", "").strip()
        old_password = request.POST.get("old_password", "")
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        error = None

        # --- Username tekshiruvi ---
        if not username:
            error = "Foydalanuvchi nomi bo‘sh bo‘lishi mumkin emas."
        elif username != user.username:
            try:
                UnicodeUsernameValidator()(username)
            except ValidationError:
                error = "Login faqat harf, raqam va @ . + - _ belgilaridan iborat bo‘lishi kerak."
            else:
                if User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
                    error = "Bu login band, boshqasini tanlang."

        # --- Parol tekshiruvi (faqat biror maydon to'ldirilgan bo'lsa) ---
        change_password = bool(old_password or new_password or confirm_password)
        if not error and change_password:
            if not user.check_password(old_password):
                error = "Joriy parol noto‘g‘ri."
            elif len(new_password) < 8:
                error = "Yangi parol kamida 8 ta belgidan iborat bo‘lishi kerak."
            elif new_password != confirm_password:
                error = "Yangi parollar mos kelmadi."
            elif new_password == old_password:
                error = "Yangi parol joriy paroldan farq qilishi kerak."

        if error:
            messages.error(request, error)
            # Kiritilgan qiymatlar formada qolishi uchun (bazaga saqlanmaydi)
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.username = username
            return render(
                request,
                "asosiy/profil.html",
                {"profile": profile, "user_profile": user},
            )

        # 1. User ma'lumotlarini yangilash
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.username = username
        if change_password:
            user.set_password(new_password)
        user.save()

        if change_password:
            # Parol o'zgargach foydalanuvchi tizimdan chiqib ketmasligi uchun
            update_session_auth_hash(request, user)

        # 2. Profil ma'lumotlarini yangilash
        profile.phone_number = request.POST.get("phone_number", "").strip()

        # Rasm yuklangan bo'lsa saqlaymiz
        if request.FILES.get("rasm"):
            profile.rasm = request.FILES["rasm"]

        profile.save()

        messages.success(
            request,
            "Profil ma’lumotlari muvaffaqiyatli saqlandi."
        )

        return redirect("profil")

    return render(
        request,
        "asosiy/profil.html",
        {
            "profile": profile,
            "user_profile": user,
        }
    )


@crm_admin_required
def admin_profile(request):
    profile, _ = Profil.objects.get_or_create(user=request.user)
    form = AdminProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
    )

    if request.method == "POST" and form.is_valid():
        profile = form.save()
        user = request.user
        user.first_name = profile.first_name.strip()
        user.last_name = profile.last_name.strip()
        user.email = profile.email.strip()
        full_name = f"{user.first_name} {user.last_name}".strip()
        if full_name:
            user.full_name = full_name
        user.save(update_fields=["first_name", "last_name", "email", "full_name"])
        messages.success(request, "Admin profilingiz muvaffaqiyatli saqlandi.")
        return redirect("admin_profile")

    return render(
        request,
        "asosiy/admin_profile.html",
        {"form": form, "admin_user": request.user, "profile": profile},
    )


def admin_login(request):
    """Authenticate staff / admin users for the separate CRM admin panel."""
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser or getattr(request.user, "role", None) == User.Role.ADMIN:
            return redirect("admin_panel")
        return redirect("index")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            if user.is_staff or user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN:
                login(request, user)
                next_url = request.GET.get("next") or request.POST.get("next")
                if next_url:
                    return redirect(next_url)
                return redirect("admin_panel")
            else:
                form.add_error(None, "Bu hisobda admin panelga kirish huquqi yo‘q.")
                return render(request, "asosiy/admin_login.html", {"form": form, "error": "Bu hisobda admin panelga kirish huquqi yo‘q."})

        # Agar username to'g'ri kelmasa, email yoki telefon orqali tekshirish
        username_val = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = None

        if "@" in username_val:
            try:
                user_obj = User.objects.get(email__iexact=username_val)
                user = authenticate(request, username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass
        elif username_val:
            clean_phone = re.sub(r'[\s\-\(\)]', '', username_val)
            if not clean_phone.startswith("+"):
                if clean_phone.startswith("998"):
                    clean_phone = "+" + clean_phone
                elif len(clean_phone) == 9:
                    clean_phone = "+998" + clean_phone
            try:
                user_obj = User.objects.get(phone=clean_phone)
                user = authenticate(request, username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass

        if user is not None:
            if user.is_staff or user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN:
                login(request, user)
                next_url = request.GET.get("next") or request.POST.get("next")
                if next_url:
                    return redirect(next_url)
                return redirect("admin_panel")
            else:
                return render(request, "asosiy/admin_login.html", {"form": form, "error": "Bu hisobda admin panelga kirish huquqi yo‘q."})

    return render(request, "asosiy/admin_login.html", {"form": form})


@require_POST
def admin_logout(request):
    """Log out of the custom CRM admin panel."""
    logout(request)
    return redirect("admin_login")