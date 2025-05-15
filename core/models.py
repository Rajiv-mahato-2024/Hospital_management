from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_phone_number(value):
    if not value.isdigit():
        raise ValidationError(_('Phone number must contain only digits'))
    if len(value) < 10:
        raise ValidationError(_('Phone number must be at least 10 digits long'))

class Patient(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient')
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Enter a valid phone number"
    )
    address = models.TextField()
    date_of_birth = models.DateField(help_text="Format: YYYY-MM-DD")
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES)
    emergency_contact = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Emergency contact phone number"
    )
    emergency_contact_name = models.CharField(max_length=100)
    allergies = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['phone']),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def age(self):
        return (timezone.now().date() - self.date_of_birth).days // 365

    def clean(self):
        if self.date_of_birth and self.date_of_birth > timezone.now().date():
            raise ValidationError(_('Date of birth cannot be in the future'))

    def get_active_appointments(self):
        return self.appointments.filter(
            appointment_date__gte=timezone.now().date(),
            status__in=['PENDING', 'CONFIRMED']
        )

class Doctor(models.Model):
    SPECIALIZATION_CHOICES = [
        ('GENERAL', 'General Physician'),
        ('CARDIOLOGY', 'Cardiology'),
        ('NEUROLOGY', 'Neurology'),
        ('PEDIATRICS', 'Pediatrics'),
        ('DERMATOLOGY', 'Dermatology'),
        ('ORTHOPEDICS', 'Orthopedics'),
        ('GYNECOLOGY', 'Gynecology'),
        ('OPHTHALMOLOGY', 'Ophthalmology'),
        ('DENTISTRY', 'Dentistry'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor')
    specialization = models.CharField(max_length=100, choices=SPECIALIZATION_CHOICES)
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Enter a valid phone number"
    )
    address = models.TextField()
    experience = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Years of experience (0-50)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['specialization', 'user__first_name']
        indexes = [
            models.Index(fields=['specialization']),
            models.Index(fields=['is_available']),
        ]

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"

    def get_available_slots(self, date):
        from datetime import timedelta
        slots = []
        start_time = timezone.datetime.strptime('09:00', '%H:%M').time()
        end_time = timezone.datetime.strptime('17:00', '%H:%M').time()
        current_time = start_time

        while current_time < end_time:
            if not self.appointments.filter(
                appointment_date=date,
                appointment_time=current_time,
                status__in=['PENDING', 'CONFIRMED']
            ).exists():
                slots.append(current_time)
            current_time = (timezone.datetime.combine(timezone.now().date(), current_time) + 
                          timedelta(minutes=30)).time()
        return slots

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)
    duration = models.IntegerField(
        default=30,
        validators=[MinValueValidator(15), MaxValueValidator(120)],
        help_text="Duration in minutes"
    )

    class Meta:
        ordering = ['-appointment_date', '-appointment_time']
        unique_together = ['doctor', 'appointment_date', 'appointment_time']
        indexes = [
            models.Index(fields=['appointment_date', 'appointment_time']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.patient} - {self.doctor} - {self.appointment_date}"

    def clean(self):
        if self.appointment_date < timezone.now().date():
            raise ValidationError(_('Cannot create appointment in the past'))
        
        if not self.doctor.is_available:
            raise ValidationError(_('Doctor is not available for appointments'))
        
        # Check for overlapping appointments
        overlapping = Appointment.objects.filter(
            doctor=self.doctor,
            appointment_date=self.appointment_date,
            appointment_time=self.appointment_time,
            status__in=['PENDING', 'CONFIRMED']
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError(_('This time slot is already booked'))

    def is_past(self):
        return self.appointment_date < timezone.now().date()

    def get_end_time(self):
        from datetime import timedelta
        return (timezone.datetime.combine(self.appointment_date, self.appointment_time) + 
                timedelta(minutes=self.duration)).time()

class MedicalRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='medical_records')
    diagnosis = models.TextField()
    prescription = models.TextField()
    notes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    follow_up_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient']),
            models.Index(fields=['doctor']),
        ]

    def __str__(self):
        return f"{self.patient} - {self.created_at.date()}"

    def clean(self):
        if self.follow_up_date and self.follow_up_date < timezone.now().date():
            raise ValidationError(_('Follow-up date cannot be in the past'))

class Bill(models.Model):
    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partial Payment'),
        ('OVERDUE', 'Overdue'),
    ]

    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('INSURANCE', 'Insurance'),
        ('ONLINE', 'Online Payment'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='bills')
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='bill')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    due_date = models.DateField(default=timezone.now)
    insurance_provider = models.CharField(max_length=100, blank=True, null=True)
    insurance_policy_number = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.patient} - ${self.amount}"

    def clean(self):
        if self.paid_amount > self.amount:
            raise ValidationError(_('Paid amount cannot be greater than total amount'))
        
        if self.paid and self.paid_amount < self.amount:
            raise ValidationError(_('Cannot mark as paid when amount is not fully paid'))

    def save(self, *args, **kwargs):
        if self.paid_amount >= self.amount:
            self.paid = True
            self.payment_status = 'PAID'
        elif self.paid_amount > 0:
            self.payment_status = 'PARTIAL'
        elif self.due_date < timezone.now().date():
            self.payment_status = 'OVERDUE'
        super().save(*args, **kwargs)

    def get_remaining_amount(self):
        return self.amount - self.paid_amount

    def is_overdue(self):
        return self.due_date < timezone.now().date() and not self.paid

class Employee(models.Model):
    POSITION_CHOICES = [
        ('RECEPTIONIST', 'Receptionist'),
        ('NURSE', 'Nurse'),
        ('PHARMACIST', 'Pharmacist'),
        ('LAB_TECH', 'Lab Technician'),
        ('ADMIN', 'Administrative Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Enter a valid phone number"
    )
    address = models.TextField()
    position = models.CharField(max_length=100, choices=POSITION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['position', 'user__first_name']
        indexes = [
            models.Index(fields=['position']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.position}"

class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='adminprofile')
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Enter a valid phone number"
    )
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_super_admin = models.BooleanField(default=False)

    class Meta:
        ordering = ['user__first_name']
        indexes = [
            models.Index(fields=['is_super_admin']),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"
