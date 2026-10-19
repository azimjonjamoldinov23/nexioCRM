import os
from datetime import date, time
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from django.template.loader import get_template, render_to_string
from django.utils import translation
from django.utils.translation import gettext
from django.conf import settings

from asosiy.models import Student
from asosiy.views import (
    admin_attendance,
    admin_group_create,
    admin_group_edit,
    admin_groups,
    admin_panel,
    admin_students,
)
from asosiy.admin import GroupAdmin, StudentAdmin
from asosiy.admin_utils import UzbekModelAdmin
from foydalanuvchilar.admin import DirectionAdmin, ProfilAdmin, UserAdmin
from .models import Profil, User
from .telegram_integration import (
    TelegramIntegrationConfigError,
    _send_message,
    notify_admin_new_registration,
)
from .views import admin_login, admin_profile, login_view, register as register_view


class SeparateAdminLoginTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_regular_login_links_to_separate_admin_login(self):
        request = self.factory.get(reverse("login"))
        request.user = AnonymousUser()

        response = login_view(request)

        self.assertContains(response, "Admin panelga kirish")
        self.assertContains(response, reverse("admin_login"))
        self.assertNotContains(response, "Siz adminsizmi?")

    def test_custom_admin_pages_have_separate_urls(self):
        self.assertEqual(reverse("admin_login"), "/boshqaruv/kirish/")
        self.assertEqual(reverse("admin_panel"), "/boshqaruv/")
        self.assertEqual(reverse("admin_groups"), "/boshqaruv/guruhlar/")
        self.assertEqual(reverse("admin_group_create"), "/boshqaruv/guruhlar/yangi/")
        self.assertEqual(reverse("admin_group_edit", args=[1]), "/boshqaruv/guruhlar/1/")
        self.assertEqual(reverse("admin_students"), "/boshqaruv/oquvchilar/")
        self.assertEqual(reverse("admin_attendance"), "/boshqaruv/davomat/")

    def test_custom_admin_pages_require_staff_access(self):
        for view, route_name in (
            (admin_panel, "admin_panel"),
            (admin_groups, "admin_groups"),
            (admin_group_create, "admin_group_create"),
            (admin_students, "admin_students"),
            (admin_attendance, "admin_attendance"),
        ):
            with self.subTest(route=route_name):
                request = self.factory.get(reverse(route_name))
                request.user = AnonymousUser()

                response = view(request)

                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("admin_login")))

        request = self.factory.get(reverse("admin_group_edit", args=[1]))
        request.user = AnonymousUser()
        response = admin_group_edit(request, 1)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("admin_login")))

    def test_custom_admin_login_uses_its_own_route_and_template(self):
        html = render_to_string(
            "asosiy/admin_login.html",
            {"form": AuthenticationForm()},
            request=self.factory.get(reverse("admin_login")),
        )
        self.assertIn("Admin panelga kirish", html)
        self.assertIn(f'action="{reverse("admin_login")}"', html)
        self.assertIn('name="username"', html)
        self.assertIn('name="password"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)

    @patch("foydalanuvchilar.views.login")
    @patch("foydalanuvchilar.views.AuthenticationForm")
    def test_custom_admin_login_sends_staff_user_to_custom_dashboard(
        self,
        authentication_form,
        login,
    ):
        user = User(username="crm_admin", is_staff=True)
        form = authentication_form.return_value
        form.is_valid.return_value = True
        form.get_user.return_value = user
        request = self.factory.post(reverse("admin_login"), {})
        request.user = AnonymousUser()

        response = admin_login(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_panel"))
        login.assert_called_once_with(request, user)

    def test_admin_language_and_crm_labels_are_uzbek(self):
        self.assertEqual(settings.LANGUAGE_CODE, "uz")
        with translation.override("uz"):
            self.assertEqual(gettext("Add"), "Qo'shish")
            self.assertEqual(gettext("Save"), "Saqlash")

        self.assertEqual(Student._meta.verbose_name, "O‘quvchi")
        self.assertEqual(Student._meta.verbose_name_plural, "O‘quvchilar")

    def test_student_admin_form_labels_are_uzbek(self):
        request = self.factory.get("/admin/asosiy/student/")
        model_admin = StudentAdmin(Student, admin.site)

        field = Student._meta.get_field("birth_date")
        formfield = model_admin.formfield_for_dbfield(field, request)

        self.assertEqual(formfield.label, "Tug‘ilgan sana")

    def test_crm_model_lists_use_the_single_row_management_template(self):
        model_admins = (
            GroupAdmin,
            StudentAdmin,
            DirectionAdmin,
            ProfilAdmin,
            UserAdmin,
        )
        for model_admin in model_admins:
            with self.subTest(model_admin=model_admin.__name__):
                self.assertEqual(
                    model_admin.change_list_template,
                    "admin/crm_change_list.html",
                )

        get_template("admin/crm_change_list.html")
        get_template("asosiy/admin_profile.html")
        self.assertEqual(reverse("admin_profile"), "/boshqaruv/profil/")

    def test_custom_group_list_renders_each_group_as_a_row(self):
        request = self.factory.get(reverse("admin_groups"))
        request.user = User(username="crm_admin", full_name="CRM Admin")
        group = SimpleNamespace(
            name="Matematika A",
            subject="Matematika",
            teacher=SimpleNamespace(full_name="Ali Valiyev", username="ali"),
            start_date=date(2026, 1, 1),
            lesson_days="Du/Cho/Ju",
            lesson_time=time(10, 30),
            room="101",
            id=17,
            active_students_count=12,
            is_active=True,
        )

        html = render_to_string(
            "asosiy/admin.html",
            {"page": "groups", "groups": [group], "groups_count": 1, "query": ""},
            request=request,
        )

        self.assertIn("Matematika A", html)
        self.assertIn("Ali Valiyev", html)
        self.assertIn("12", html)
        self.assertIn(reverse("admin_group_create"), html)
        self.assertIn(reverse("admin_group_edit", args=[17]), html)
        self.assertIn("+ Yangi guruh ochish", html)
        self.assertIn("Boshqarish", html)
        self.assertEqual(html.count("<tbody>"), 1)
        self.assertEqual(html.count("<tr>"), 2)

    def test_custom_student_list_renders_each_student_as_a_row(self):
        request = self.factory.get(reverse("admin_students"))
        request.user = User(username="crm_admin", full_name="CRM Admin")
        student = SimpleNamespace(
            user=SimpleNamespace(
                full_name="Vali Aliyev",
                username="vali",
                phone="+998901234567",
                email="vali@example.com",
            ),
            active_groups_count=2,
            created_at=date(2026, 1, 1),
        )

        html = render_to_string(
            "asosiy/admin.html",
            {"page": "students", "students": [student], "students_count": 1, "query": ""},
            request=request,
        )

        self.assertIn("Vali Aliyev", html)
        self.assertIn("+998901234567", html)
        self.assertIn("vali@example.com", html)
        self.assertEqual(html.count("<tbody>"), 1)
        self.assertEqual(html.count("<tr>"), 2)

    def test_custom_admin_template_has_attendance_taking_controls(self):
        request = self.factory.get(reverse("admin_attendance"))
        request.user = User(username="crm_admin", full_name="CRM Admin")
        lesson = SimpleNamespace(id=4)
        student = SimpleNamespace(
            id=9,
            user=SimpleNamespace(full_name="Vali Aliyev", username="vali", phone="+998901234567"),
            attendance_status="present",
        )

        html = render_to_string(
            "asosiy/admin.html",
            {
                "page": "attendance",
                "lessons": [],
                "lesson": lesson,
                "students": [student],
                "attendance_statuses": (
                    ("present", "Keldi"),
                    ("absent", "Kelmadi"),
                    ("late", "Kechikdi"),
                    ("excused", "Sababli"),
                ),
            },
            request=request,
        )

        self.assertIn("Davomat olish", html)
        self.assertIn('name="status_9"', html)
        self.assertIn("Davomatni saqlash", html)

    @patch("foydalanuvchilar.views.login")
    @patch("foydalanuvchilar.views.authenticate")
    def test_regular_login_keeps_existing_dashboard_behavior(self, authenticate, login):
        user = User(role=User.Role.STUDENT)
        authenticate.return_value = user
        request = self.factory.post(
            reverse("login"),
            {"username": "student", "password": "password"},
        )
        request.user = AnonymousUser()

        response = login_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("index"))
        login.assert_called_once_with(request, user)


class TelegramWebsiteIntegrationTests(IsolatedAsyncioTestCase):
    @patch("foydalanuvchilar.telegram_integration.Bot")
    async def test_new_website_registration_is_sent_to_bot_admin(self, bot_class):
        bot = bot_class.return_value.__aenter__.return_value

        await _send_message("test-token", "123456", "Yangi o‘quvchi")

        bot_class.assert_called_once_with(token="test-token")
        bot.send_message.assert_awaited_once_with(
            chat_id="123456",
            text="Yangi o‘quvchi",
        )

    @patch("foydalanuvchilar.views.login")
    @patch("foydalanuvchilar.views.notify_admin_new_registration")
    @patch("foydalanuvchilar.views.RegisterForm")
    def test_website_signup_triggers_admin_bot_notification(
        self,
        form_class,
        notify_admin,
        login,
    ):
        user = User(
            username="new_student",
            full_name="Yangi O‘quvchi",
            phone="+998901234567",
        )
        form = form_class.return_value
        form.is_valid.return_value = True
        form.save.return_value = user
        request = RequestFactory().post(reverse("register"), {})
        request.user = AnonymousUser()

        response = register_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("index"))
        notify_admin.assert_called_once_with(user)
        login.assert_called_once_with(request, user)

    @patch.dict(os.environ, {"BOT_TOKEN": "", "ADMIN_TELEGRAM_ID": ""})
    def test_website_registration_reports_missing_bot_configuration(self):
        user = User(
            username="new_student",
            full_name="Yangi O‘quvchi",
            phone="+998901234567",
        )

        with self.assertRaises(TelegramIntegrationConfigError):
            notify_admin_new_registration(user)


class AdminProfileTests(SimpleTestCase):
    @patch("foydalanuvchilar.views.Profil.objects.get_or_create")
    def test_admin_profile_page_creates_and_displays_admin_profile(self, get_or_create):
        user = User(username="crm_admin", full_name="CRM Admin", is_staff=True, is_active=True)
        profile = Profil(user=user)
        get_or_create.return_value = (profile, True)
        request = RequestFactory().get(reverse("admin_profile"))
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = admin_profile(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin profilim")
        get_or_create.assert_called_once_with(user=user)

    @patch("foydalanuvchilar.views.AdminProfileForm")
    @patch("foydalanuvchilar.views.Profil.objects.get_or_create")
    def test_admin_profile_form_saves_profile_and_user_name(
        self,
        get_or_create,
        form_class,
    ):
        user = User(username="crm_admin", full_name="CRM Admin", is_staff=True, is_active=True)
        profile = Profil(
            user=user,
            first_name="Yangi",
            last_name="Admin",
            email="admin@example.com",
        )
        get_or_create.return_value = (profile, False)
        form = form_class.return_value
        form.is_valid.return_value = True
        form.save.return_value = profile
        user.save = Mock()
        request = RequestFactory().post(reverse("admin_profile"), {})
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = admin_profile(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_profile"))
        self.assertEqual(user.full_name, "Yangi Admin")
        user.save.assert_called_once_with(
            update_fields=["first_name", "last_name", "email", "full_name"]
        )
