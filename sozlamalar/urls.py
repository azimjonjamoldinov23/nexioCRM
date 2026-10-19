from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from asosiy.views import (
    admin_groups,
    admin_group_create,
    admin_group_delete,
    admin_group_edit,
    admin_group_students,
    admin_lesson_create,
    admin_attendance,
    admin_panel,
    admin_payments,
    admin_payment_create,
    admin_payment_delete,
    admin_students,
    admin_student_create,
    admin_student_enroll,
    admin_student_delete,
    admin_teachers,
    admin_teacher_create,
    admin_teacher_delete,
    admin_arizalar,
    admin_ariza_status,
    admin_ariza_delete,
    index,
)
from foydalanuvchilar.views import admin_login, admin_logout, admin_profile


urlpatterns = [
    path("boshqaruv/kirish/", admin_login, name="admin_login"),
    path("boshqaruv/chiqish/", admin_logout, name="admin_logout"),
    path("boshqaruv/profil/", admin_profile, name="admin_profile"),
    path("boshqaruv/arizalar/", admin_arizalar, name="admin_arizalar"),
    path("boshqaruv/arizalar/<int:ariza_id>/status/<str:new_status>/", admin_ariza_status, name="admin_ariza_status"),
    path("boshqaruv/arizalar/<int:ariza_id>/ochirish/", admin_ariza_delete, name="admin_ariza_delete"),
    path("boshqaruv/guruhlar/", admin_groups, name="admin_groups"),
    path("boshqaruv/guruhlar/yangi/", admin_group_create, name="admin_group_create"),
    path("boshqaruv/guruhlar/<int:group_id>/oquvchilar/", admin_group_students, name="admin_group_students"),
    path("boshqaruv/guruhlar/<int:group_id>/ochirish/", admin_group_delete, name="admin_group_delete"),
    path("boshqaruv/guruhlar/<int:group_id>/", admin_group_edit, name="admin_group_edit"),
    path("boshqaruv/darslar/yangi/", admin_lesson_create, name="admin_lesson_create"),
    path("boshqaruv/tolovlar/", admin_payments, name="admin_payments"),
    path("boshqaruv/tolovlar/yangi/", admin_payment_create, name="admin_payment_create"),
    path("boshqaruv/tolovlar/<int:payment_id>/ochirish/", admin_payment_delete, name="admin_payment_delete"),
    path("boshqaruv/oquvchilar/", admin_students, name="admin_students"),
    path("boshqaruv/oquvchilar/yangi/", admin_student_create, name="admin_student_create"),
    path("boshqaruv/oquvchilar/<int:student_id>/biriktirish/", admin_student_enroll, name="admin_student_enroll"),
    path("boshqaruv/oquvchilar/<int:student_id>/ochirish/", admin_student_delete, name="admin_student_delete"),
    path("boshqaruv/oqituvchilar/", admin_teachers, name="admin_teachers"),
    path("boshqaruv/oqituvchilar/yangi/", admin_teacher_create, name="admin_teacher_create"),
    path("boshqaruv/oqituvchilar/<int:teacher_id>/ochirish/", admin_teacher_delete, name="admin_teacher_delete"),
    path("boshqaruv/davomat/", admin_attendance, name="admin_attendance"),
    path("boshqaruv/", admin_panel, name="admin_panel"),
    path("admin/", admin.site.urls),
    path("", include("foydalanuvchilar.urls")),
    path("dashboard/", index, name="index"),
]


# MEDIA fayllar uchun
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )