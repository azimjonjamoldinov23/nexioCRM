from django.urls import path

from asosiy.views import guruhga_yozilish, guruhlarim, guruhdan_chiqish, darslarim
from .views import chat, davomatim, login_view, profil, register, logout_view, reytinglarim, tolovlarim

urlpatterns = [
    path("", login_view, name="login"),
    path("register/", register, name="register"),
    path("logout/", logout_view, name="logout"),
    path("guruhlarim/", guruhlarim, name="guruhlarim"),
    path("guruhga_yozilish/<int:group_id>/", guruhga_yozilish, name="guruhga_yozilish"),
    path("guruhdan_chiqish/<int:group_id>/", guruhdan_chiqish, name="guruhdan_chiqish"),
    path("darslarim/", darslarim, name="darslarim"),
    path("davomatim/", davomatim, name="davomatim"),
    path("reyting/", reytinglarim, name="reyting"),
    path("tolov/", tolovlarim, name="tolov"),
    path("chat/", chat, name="chat"),
    path("profil/", profil, name="profil"),
]