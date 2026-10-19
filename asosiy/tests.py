from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from foydalanuvchilar.models import User

from .models import Attendance, Enrollment, Group, Lesson, Payment, Student


class AdminAttendanceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="test-password",
            full_name="CRM Admin",
            role=User.Role.ADMIN,
            phone="+998900000001",
            is_staff=True,
        )
        self.teacher = User.objects.create_user(
            username="teacher",
            password="test-password",
            full_name="Test Teacher",
            role=User.Role.TEACHER,
            phone="+998900000002",
        )
        self.student_user = User.objects.create_user(
            username="student",
            password="test-password",
            full_name="Test Student",
            role=User.Role.STUDENT,
            phone="+998900000003",
        )
        self.student = Student.objects.create(user=self.student_user)
        self.group = Group.objects.create(
            name="A-01",
            subject="Matematika",
            teacher=self.teacher,
            monthly_price=Decimal("300000"),
            start_date=date(2026, 1, 1),
            lesson_days="Du Cho Ju",
            lesson_time="10:00",
            room="1",
        )
        self.client.force_login(self.admin)

    def test_admin_can_create_lesson_from_attendance_workflow(self):
        response = self.client.post(
            reverse("admin_lesson_create"),
            {
                "group": self.group.pk,
                "date": timezone.localdate().isoformat(),
                "topic": "Kasrlar",
                "is_held": "on",
                "cancel_reason": "",
            },
        )

        lesson = Lesson.objects.get(group=self.group)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('admin_attendance')}?lesson={lesson.pk}")
        self.assertEqual(lesson.created_by, self.admin)

    def test_admin_can_save_attendance_for_active_student(self):
        lesson = Lesson.objects.create(
            group=self.group,
            date=timezone.localdate(),
            topic="Kasrlar",
            created_by=self.admin,
        )
        Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=lesson.date,
            status=Enrollment.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("admin_attendance"),
            {
                "lesson_id": lesson.pk,
                f"status_{self.student.pk}": Attendance.Status.LATE,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Attendance.objects.get(lesson=lesson, student=self.student).status,
            Attendance.Status.LATE,
        )

    def test_group_selection_creates_todays_lesson_and_saves_attendance(self):
        lesson_date = timezone.localdate()
        Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=lesson_date,
            status=Enrollment.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("admin_attendance"),
            {
                "group_id": self.group.pk,
                "lesson_date": lesson_date.isoformat(),
                f"status_{self.student.pk}": Attendance.Status.PRESENT,
            },
        )

        lesson = Lesson.objects.get(group=self.group, date=lesson_date)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Attendance.objects.get(lesson=lesson, student=self.student).status,
            Attendance.Status.PRESENT,
        )
        self.assertEqual(lesson.created_by, self.admin)

    def test_attendance_page_lists_active_groups_and_roster(self):
        Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=timezone.localdate(),
            status=Enrollment.Status.ACTIVE,
        )

        response = self.client.get(
            reverse("admin_attendance"),
            {"group": self.group.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_group"], self.group)
        self.assertContains(response, "A-01")
        self.assertContains(response, "Test Student")

    def test_student_attendance_page_shows_saved_attendance(self):
        lesson = Lesson.objects.create(
            group=self.group,
            date=timezone.localdate(),
            topic="Kasrlar",
            created_by=self.admin,
        )
        Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=lesson.date,
            status=Enrollment.Status.ACTIVE,
        )
        Attendance.objects.create(
            lesson=lesson,
            student=self.student,
            status=Attendance.Status.PRESENT,
            marked_by=self.admin,
        )

        self.client.force_login(self.student_user)
        response = self.client.get(reverse("davomatim"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jami_darslar"], 1)
        self.assertEqual(response.context["qatnashgan"], 1)
        self.assertContains(response, "Kasrlar")

    def test_student_payment_page_uses_recorded_payments(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=timezone.localdate(),
            status=Enrollment.Status.ACTIVE,
        )
        Payment.objects.create(
            enrollment=enrollment,
            amount=Decimal("300000"),
            period=date(2026, 10, 1),
            paid_at=timezone.localdate(),
            method=Payment.Method.CASH,
            created_by=self.admin,
        )

        self.client.force_login(self.student_user)
        response = self.client.get(reverse("tolov"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jami_tolov"], Decimal("300000"))
        self.assertEqual(response.context["muvaffaqiyatli_tolovlar"], 1)
        self.assertContains(response, "Naqd")
        self.assertContains(response, "A-01")

    def test_student_chat_and_payment_pages_share_navigation(self):
        self.client.force_login(self.student_user)

        for page_name, active_url in (("chat", "/chat/"), ("tolov", "/tolov/")):
            with self.subTest(page=page_name):
                response = self.client.get(reverse(page_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'href="/davomatim/"')
                self.assertContains(response, 'href="/reyting/"')
                self.assertContains(response, 'href="/chat/"')
                self.assertContains(response, 'href="/tolov/"')
                self.assertContains(response, f'href="{active_url}" class="active"')

    def test_admin_can_record_payment_for_active_enrollment(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=timezone.localdate(),
            status=Enrollment.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("admin_payment_create"),
            {
                "enrollment": enrollment.pk,
                "amount": "300000",
                "period": "2026-10-16",
                "paid_at": "2026-10-16",
                "method": Payment.Method.CASH,
                "receipt_no": "K-100",
            },
        )

        payment = Payment.objects.get(enrollment=enrollment)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_payments"))
        self.assertEqual(payment.created_by, self.admin)
        self.assertEqual(payment.period, date(2026, 10, 1))

    def test_group_students_page_lists_members_and_payment_totals(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=timezone.localdate(),
            status=Enrollment.Status.ACTIVE,
        )
        Payment.objects.create(
            enrollment=enrollment,
            amount=Decimal("125000"),
            period=date(2026, 10, 1),
            paid_at=timezone.localdate(),
            method=Payment.Method.CASH,
            created_by=self.admin,
        )

        response = self.client.get(
            reverse("admin_group_students", args=[self.group.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_students_count"], 1)
        self.assertContains(response, "Test Student")
        self.assertContains(response, "125000")

    def test_group_with_enrollment_is_archived_instead_of_deleting_history(self):
        Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=timezone.localdate(),
            status=Enrollment.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("admin_group_delete", args=[self.group.pk])
        )

        self.group.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.group.is_active)
        self.assertTrue(self.group.enrollments.exists())

    def test_group_without_enrollments_can_be_deleted(self):
        response = self.client.post(
            reverse("admin_group_delete", args=[self.group.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Group.objects.filter(pk=self.group.pk).exists())

    def test_group_delete_requires_post(self):
        response = self.client.get(
            reverse("admin_group_delete", args=[self.group.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Group.objects.filter(pk=self.group.pk).exists())

    def test_admin_can_create_teacher_account(self):
        response = self.client.post(
            reverse("admin_teacher_create"),
            {
                "username": "newteacher",
                "full_name": "New Teacher",
                "phone": "+998900000004",
                "email": "teacher@example.com",
                "password": "securepass123",
            },
        )

        teacher = User.objects.get(username="newteacher")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_teachers"))
        self.assertEqual(teacher.role, User.Role.TEACHER)
        self.assertTrue(teacher.check_password("securepass123"))
        self.assertFalse(teacher.is_staff)

    def test_teacher_management_pages_render(self):
        list_response = self.client.get(reverse("admin_teachers"))
        create_response = self.client.get(reverse("admin_teacher_create"))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "O‘qituvchilar")
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, "Yangi o‘qituvchi qo‘shish")

    def test_admin_can_create_group_and_assign_teacher(self):
        response = self.client.post(
            reverse("admin_group_create"),
            {
                "name": "B-02",
                "subject": "Ingliz tili",
                "teacher": self.teacher.pk,
                "monthly_price": "250000",
                "start_date": "2026-10-16",
                "end_date": "",
                "lesson_days": "Du Cho Ju",
                "lesson_time": "12:00",
                "room": "2",
                "is_active": "on",
            },
        )

        group = Group.objects.get(name="B-02")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(group.teacher, self.teacher)
        self.assertRedirects(response, reverse("admin_groups"))

    def test_teacher_with_group_history_is_deactivated_not_deleted(self):
        response = self.client.post(
            reverse("admin_teacher_delete", args=[self.teacher.pk])
        )

        self.teacher.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.teacher.is_active)
        self.assertTrue(Group.objects.filter(teacher=self.teacher).exists())
