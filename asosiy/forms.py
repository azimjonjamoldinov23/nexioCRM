from django import forms
from django.core.validators import MinLengthValidator

from foydalanuvchilar.models import User

from .models import Enrollment, Group, Lesson, Payment


class AdminGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = (
            "name",
            "subject",
            "teacher",
            "monthly_price",
            "start_date",
            "end_date",
            "lesson_days",
            "lesson_time",
            "room",
            "is_active",
        )
        labels = {
            "name": "Guruh nomi",
            "subject": "Fan",
            "teacher": "O‘qituvchi",
            "monthly_price": "Oylik to‘lov",
            "start_date": "Boshlanish sanasi",
            "end_date": "Tugash sanasi",
            "lesson_days": "Dars kunlari",
            "lesson_time": "Dars vaqti",
            "room": "Xona",
            "is_active": "Faol guruh",
        }
        widgets = {
            "monthly_price": forms.NumberInput(attrs={"min": "0", "step": "1000"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "lesson_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = User.objects.filter(
            role=User.Role.TEACHER,
            is_active=True,
        ).order_by("full_name")


class AdminLessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ("group", "date", "topic", "is_held", "cancel_reason")
        labels = {
            "group": "Guruh",
            "date": "Dars sanasi",
            "topic": "Dars mavzusi",
            "is_held": "Dars o‘tkazildi",
            "cancel_reason": "Bekor qilish sababi",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "topic": forms.TextInput(attrs={"placeholder": "Masalan: 3-mavzu — Kasrlar"}),
            "cancel_reason": forms.TextInput(attrs={"placeholder": "Faqat bekor qilingan dars uchun"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = Group.objects.filter(
            is_active=True
        ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_held") is False and not cleaned_data.get("cancel_reason"):
            self.add_error("cancel_reason", "Bekor qilingan dars sababini kiriting.")
        return cleaned_data


class AdminPaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("enrollment", "amount", "period", "paid_at", "method", "receipt_no")
        labels = {
            "enrollment": "O‘quvchi va guruh",
            "amount": "To‘lov summasi",
            "period": "To‘lov davri",
            "paid_at": "To‘langan sana",
            "method": "To‘lov usuli",
            "receipt_no": "Kvitansiya raqami",
        }
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "1000"}),
            "period": forms.DateInput(attrs={"type": "date"}),
            "paid_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["enrollment"].queryset = Enrollment.objects.filter(
            status=Enrollment.Status.ACTIVE
        ).select_related("student__user", "group").order_by(
            "student__user__full_name", "group__name"
        )
        self.fields["enrollment"].label_from_instance = (
            lambda enrollment: f"{enrollment.student.user.full_name} — {enrollment.group.name}"
        )


class AdminTeacherForm(forms.ModelForm):
    password = forms.CharField(
        label="Parol",
        widget=forms.PasswordInput,
        validators=[MinLengthValidator(8, "Parol kamida 8 ta belgidan iborat bo‘lsin.")],
    )

    class Meta:
        model = User
        fields = ("username", "full_name", "phone", "email")
        labels = {
            "username": "Login",
            "full_name": "F.I.Sh",
            "phone": "Telefon",
            "email": "Elektron pochta",
        }
        widgets = {
            "email": forms.EmailInput(),
            "phone": forms.TextInput(attrs={"placeholder": "+998901234567"}),
        }

    def save(self, commit=True):
        teacher = super().save(commit=False)
        teacher.role = User.Role.TEACHER
        teacher.is_active = True
        teacher.set_password(self.cleaned_data["password"])
        if commit:
            teacher.save()
        return teacher


class AdminStudentForm(forms.ModelForm):
    full_name = forms.CharField(label="F.I.Sh (Ism Familiya)", max_length=200)
    phone = forms.CharField(
        label="Telefon raqami",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "+998901234567"}),
    )
    email = forms.EmailField(label="Elektron pochta", required=False)
    username = forms.CharField(
        label="Login (Username)",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "masalan: aliyev_o"}),
    )
    password = forms.CharField(
        label="Boshlang‘ich parol",
        widget=forms.PasswordInput,
        required=False,
        help_text="Bo‘sh qoldirilsa, standart '123456' qo‘yiladi.",
    )
    parent_name = forms.CharField(label="Ota-onasining ismi", max_length=200, required=False)
    parent_phone = forms.CharField(label="Ota-onasining telefoni", max_length=20, required=False)
    address = forms.CharField(label="Yashash manzili", max_length=255, required=False)
    note = forms.CharField(label="Izoh / Qo‘shimcha ma’lumot", widget=forms.Textarea(attrs={"rows": 2}), required=False)

    class Meta:
        model = User
        fields = ("full_name", "username", "phone", "email")

    def clean_phone(self):
        import re
        raw_phone = self.cleaned_data.get("phone", "").strip()
        phone = re.sub(r'[\s\-\(\)]', '', raw_phone)
        if not phone.startswith("+"):
            if phone.startswith("998"):
                phone = "+" + phone
            elif len(phone) == 9:
                phone = "+998" + phone
            else:
                phone = "+" + phone
        return phone

    def save(self, commit=True):
        import re
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        user.is_active = True
        pwd = self.cleaned_data.get("password") or "123456"
        user.set_password(pwd)
        user.phone = self.cleaned_data.get("phone")

        parts = user.full_name.split(maxsplit=1)
        user.first_name = parts[0] if parts else user.username
        user.last_name = parts[1] if len(parts) > 1 else ""

        if commit:
            user.save()
            from .models import Student
            student, _ = Student.objects.get_or_create(user=user)
            student.parent_name = self.cleaned_data.get("parent_name", "")
            student.parent_phone = self.cleaned_data.get("parent_phone", "")
            student.address = self.cleaned_data.get("address", "")
            student.note = self.cleaned_data.get("note", "")
            student.save()
        return user


class AdminEnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ("student", "group", "start_date", "discount_percent", "status")
        labels = {
            "student": "O‘quvchi",
            "group": "Guruh",
            "start_date": "Darsni boshlash sanasi",
            "discount_percent": "Chegirma foizi (%)",
            "status": "A’zolik holati",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "discount_percent": forms.NumberInput(attrs={"min": "0", "max": "100"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = Group.objects.filter(is_active=True).order_by("name")
        self.fields["student"].label_from_instance = (
            lambda s: f"{s.user.full_name} (@{s.user.username})"
        )

