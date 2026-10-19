from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class Direction(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Fan / Yo‘nalish"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Faol"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Fan / Yo‘nalish"
        verbose_name_plural = "Fan / Yo‘nalishlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        TEACHER = 'teacher', "O'qituvchi"
        STUDENT = 'student', "O'quvchi"

    phone_validator = RegexValidator(
        regex=r'^\+998\d{9}$',
        message="Telefon raqami +998901234567 formatida bo'lishi kerak.",
    )

    full_name = models.CharField(max_length=200)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )

    phone = models.CharField(
        max_length=20,
        unique=True,
        validators=[phone_validator],
    )

    telegram_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self):
        return self.full_name or self.username
    

class Profil(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    first_name = models.CharField(
        max_length=100,
        blank=True
    )

    last_name = models.CharField(
        max_length=100,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True
    )

    rasm = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profillar"

    def __str__(self):
        return f"Profile of {self.user.username}"