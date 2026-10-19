from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
	MaxValueValidator,
	MinValueValidator,
)
from django.db import models
from django.utils import timezone

from foydalanuvchilar.models import User


class Group(models.Model):
	name = models.CharField(max_length=150)
	subject = models.CharField(max_length=100)
	teacher = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name='teaching_groups',
	)
	monthly_price = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		validators=[MinValueValidator(Decimal('0'))],
	)
	start_date = models.DateField()
	end_date = models.DateField(null=True, blank=True)
	lesson_days = models.CharField(max_length=20)
	lesson_time = models.TimeField()
	room = models.CharField(max_length=30)
	is_active = models.BooleanField(default=True, db_index=True)

	class Meta:
		verbose_name = "Guruh"
		verbose_name_plural = "Guruhlar"
		unique_together = ('name', 'start_date')

	def clean(self):
		if self.teacher_id and self.teacher.role != User.Role.TEACHER:
			raise ValidationError({'teacher': "Guruh o'qituvchisi teacher rolida bo'lishi kerak."})
		if self.end_date and self.end_date <= self.start_date:
			raise ValidationError({'end_date': "Yopilish sanasi boshlanish sanasidan keyin bo'lishi kerak."})

	def __str__(self):
		return self.name


class Student(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='student_profile',
	)
	birth_date = models.DateField(null=True, blank=True)
	parent_name = models.CharField(max_length=200, blank=True)
	parent_phone = models.CharField(max_length=20, blank=True)
	address = models.CharField(max_length=255, blank=True)
	note = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "O‘quvchi"
		verbose_name_plural = "O‘quvchilar"

	def clean(self):
		if self.user_id and self.user.role != User.Role.STUDENT:
			raise ValidationError({'user': "Student foydalanuvchisi student rolida bo'lishi kerak."})

	def __str__(self):
		return self.user.full_name


class Enrollment(models.Model):
	class Status(models.TextChoices):
		ACTIVE = 'active', 'Faol'
		PAUSED = 'paused', 'Toxtatilgan'
		FINISHED = 'finished', 'Yakunlangan'
		DROPPED = 'dropped', 'Chiqqan'

	student = models.ForeignKey(
		Student,
		on_delete=models.PROTECT,
		related_name='enrollments',
	)
	group = models.ForeignKey(
		Group,
		on_delete=models.PROTECT,
		related_name='enrollments',
	)
	start_date = models.DateField()
	end_date = models.DateField(null=True, blank=True)
	discount_percent = models.PositiveSmallIntegerField(
		default=0,
		validators=[MinValueValidator(0), MaxValueValidator(100)],
	)
	status = models.CharField(max_length=20, choices=Status.choices)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "Guruh a’zoligi"
		verbose_name_plural = "Guruh a’zoliklari"
		unique_together = ('student', 'group', 'start_date')
		constraints = [
			models.CheckConstraint(
				condition=models.Q(end_date__isnull=True)
				| models.Q(end_date__gte=models.F('start_date')),
				name='enrollment_end_after_start',
			),
		]
		indexes = [
			models.Index(fields=['student', 'group']),
		]

	def __str__(self):
		return f'{self.student} - {self.group}'


class Lesson(models.Model):
	group = models.ForeignKey(
		Group,
		on_delete=models.CASCADE,
		related_name='lessons',
	)
	date = models.DateField()
	topic = models.CharField(max_length=200)
	is_held = models.BooleanField(default=True)
	cancel_reason = models.CharField(max_length=200, blank=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name='created_lessons',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "Dars"
		verbose_name_plural = "Darslar"
		unique_together = ('group', 'date')
		constraints = [
		]
		indexes = [
			models.Index(fields=['group', 'date']),
		]

	def clean(self):
		if not self.is_held and not self.cancel_reason:
			raise ValidationError({'cancel_reason': "Bekor qilingan dars sababini kiriting."})

	def __str__(self):
		return f'{self.group} - {self.date}'


class Attendance(models.Model):
	class Status(models.TextChoices):
		PRESENT = 'present', 'Keldi'
		ABSENT = 'absent', 'Kelmadi'
		LATE = 'late', 'Kechikdi'
		EXCUSED = 'excused', 'Sababli'

	lesson = models.ForeignKey(
		Lesson,
		on_delete=models.CASCADE,
		related_name='attendances',
	)
	student = models.ForeignKey(
		Student,
		on_delete=models.PROTECT,
		related_name='attendances',
	)
	status = models.CharField(max_length=10, choices=Status.choices)
	comment = models.CharField(max_length=200, blank=True)
	marked_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name='marked_attendances',
	)
	marked_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = "Davomat"
		verbose_name_plural = "Davomat"
		unique_together = ('lesson', 'student')
		constraints = [
		]
		indexes = [
			models.Index(fields=['student', 'status']),
		]

	def clean(self):
		if not self.lesson.is_held:
			raise ValidationError({'lesson': "Bekor qilingan darsga davomat yozib bo'lmaydi."})
		active_enrollment = Enrollment.objects.filter(
			student=self.student,
			group=self.lesson.group,
			start_date__lte=self.lesson.date,
		).filter(
			models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.lesson.date),
			status=Enrollment.Status.ACTIVE,
		).exists()
		if not active_enrollment:
			raise ValidationError({'student': "O'quvchi ushbu guruhda faol a'zo emas."})

	def __str__(self):
		return f'{self.lesson} - {self.student}'


class Payment(models.Model):
	class Method(models.TextChoices):
		CASH = 'cash', 'Naqd'
		CARD = 'card', 'Karta'
		TRANSFER = 'transfer', "O'tkazma"

	enrollment = models.ForeignKey(
		Enrollment,
		on_delete=models.PROTECT,
		related_name='payments',
	)
	amount = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		validators=[MinValueValidator(Decimal('0.01'))],
	)
	period = models.DateField()
	paid_at = models.DateField()
	method = models.CharField(max_length=20, choices=Method.choices)
	receipt_no = models.CharField(max_length=50, blank=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name='created_payments',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "To‘lov"
		verbose_name_plural = "To‘lovlar"
		indexes = [
			models.Index(fields=['enrollment', 'period']),
		]

	def save(self, *args, **kwargs):
		self.period = self.period.replace(day=1)
		super().save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		if timezone.localdate() - self.paid_at > timedelta(days=30):
			raise ValidationError("30 kundan eski to'lovni o'chirib bo'lmaydi.")
		return super().delete(*args, **kwargs)

	def __str__(self):
		return f'{self.enrollment} - {self.amount}'


class Ariza(models.Model):
	class Status(models.TextChoices):
		YANGI = 'yangi', 'Yangi'
		BOGLANILDI = 'boglanildi', "Bog'lanildi"
		QABUL_QILINDI = 'qabul_qilindi', 'Qabul qilindi'
		BEKOR_QILINDI = 'bekor_qilindi', 'Bekor qilindi'

	full_name = models.CharField(max_length=200, verbose_name="F.I.Sh")
	phone = models.CharField(max_length=30, verbose_name="Telefon raqami")
	course = models.CharField(max_length=150, verbose_name="Kurs")
	telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name="Telegram ID", db_index=True)
	telegram_username = models.CharField(max_length=150, blank=True, verbose_name="Telegram username")
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.YANGI,
		verbose_name="Holati",
		db_index=True,
	)
	note = models.TextField(blank=True, verbose_name="Izoh")
	created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

	class Meta:
		verbose_name = "Ariza"
		verbose_name_plural = "Arizalar"
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.full_name} ({self.course})"
