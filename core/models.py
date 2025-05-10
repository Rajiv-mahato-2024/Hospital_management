from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Patient(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, help_text="Enter a valid phone number")
    address = models.TextField()
    date_of_birth = models.DateField(help_text="Format: YYYY-MM-DD")
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def age(self):
        return (timezone.now().date() - self.date_of_birth).days // 365

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

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=100, choices=SPECIALIZATION_CHOICES)
    phone = models.CharField(max_length=15, help_text="Enter a valid phone number")
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

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"

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

    class Meta:
        ordering = ['-appointment_date', '-appointment_time']
        unique_together = ['doctor', 'appointment_date', 'appointment_time']

    def __str__(self):
        return f"{self.patient} - {self.doctor} - {self.appointment_date}"

    def is_past(self):
        return self.appointment_date < timezone.now().date()

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

    def __str__(self):
        return f"{self.patient} - {self.created_at.date()}"

class Bill(models.Model):
    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partial Payment'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='bills')
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient} - ${self.amount}"

class Employee(models.Model):
    POSITION_CHOICES = [
        ('RECEPTIONIST', 'Receptionist'),
        ('NURSE', 'Nurse'),
        ('PHARMACIST', 'Pharmacist'),
        ('LAB_TECH', 'Lab Technician'),
        ('ADMIN', 'Administrative Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, help_text="Enter a valid phone number")
    address = models.TextField()
    position = models.CharField(max_length=100, choices=POSITION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['position', 'user__first_name']

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, help_text="Enter a valid phone number")
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_super_admin = models.BooleanField(default=False)

    class Meta:
        ordering = ['user__first_name']

    def __str__(self):
        return f"Admin: {self.user.first_name} {self.user.last_name}"
