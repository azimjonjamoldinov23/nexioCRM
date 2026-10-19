import re
from django import forms
from django.contrib.auth import get_user_model

from .models import Profil

User = get_user_model()


class RegisterForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=25,
        required=True,
        error_messages={
            'required': "Iltimos, telefon raqamingizni kiriting."
        }
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput,
        error_messages={
            'required': "Iltimos, parol kiriting."
        }
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput,
        error_messages={
            'required': "Iltimos, parolni qaytadan kiriting."
        }
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "phone"]
        labels = {
            "first_name": "Ism",
            "last_name": "Familiya",
            "username": "Foydalanuvchi nomi",
            "email": "Email",
            "phone": "Telefon raqami",
        }

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name", "").strip()
        if not first_name:
            raise forms.ValidationError("Iltimos, ismingizni kiriting.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name", "").strip()
        if not last_name:
            raise forms.ValidationError("Iltimos, familiyangizni kiriting.")
        return last_name

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            raise forms.ValidationError("Iltimos, foydalanuvchi nomini kiriting.")

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Bu foydalanuvchi nomi (username) allaqachon band.")

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu email manzili bilan allaqachon ro'yxatdan o'tilgan.")

        return email

    def clean_phone(self):
        raw_phone = self.cleaned_data.get("phone", "").strip()
        # Bo'sh joylar va chiziqchalarni tozalash
        phone = re.sub(r'[\s\-\(\)]', '', raw_phone)
        if not phone.startswith("+"):
            if phone.startswith("998"):
                phone = "+" + phone
            elif len(phone) == 9:
                phone = "+998" + phone
            else:
                phone = "+" + phone

        if not re.match(r'^\+998\d{9}$', phone):
            raise forms.ValidationError("Telefon raqami +998901234567 formatida bo'lishi kerak.")

        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("Ushbu telefon raqami allaqachon ro'yxatdan o'tgan.")

        return phone

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")

        if p1 and len(p1) < 4:
            self.add_error("password1", "Parol kamida 4 ta belgidan iborat bo'lishi kerak.")

        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Kiritilgan parollar bir-biriga mos kelmadi.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        first = self.cleaned_data.get("first_name", "").strip()
        last = self.cleaned_data.get("last_name", "").strip()
        user.first_name = first
        user.last_name = last
        user.full_name = f"{first} {last}".strip() or user.username
        user.role = User.Role.STUDENT
        user.phone = self.cleaned_data.get("phone", "")

        if commit:
            user.save()
            from asosiy.models import Student
            Student.objects.get_or_create(user=user)

        return user


class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = Profil
        fields = ("first_name", "last_name", "email", "phone_number", "rasm")
        labels = {
            "first_name": "Ism",
            "last_name": "Familiya",
            "email": "Elektron pochta",
            "phone_number": "Aloqa telefoni",
            "rasm": "Profil rasmi",
        }