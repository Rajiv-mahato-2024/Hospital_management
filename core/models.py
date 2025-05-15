from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import uuid

def validate_phone_number(value):
    if not value.isdigit():
        raise ValidationError(_('Phone number must contain only digits'))
    if len(value) < 10:
        raise ValidationError(_('Phone number must be at least 10 digits long'))

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Patient(BaseModel):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other')
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient')
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Enter a valid phone number",
        default=''
    )
    address = models.TextField(default='')
    date_of_birth = models.DateField(help_text="Format: YYYY-MM-DD", null=True, blank=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, default='A+')
    emergency_contact = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Emergency contact phone number",
        default=''
    )
    emergency_contact_name = models.CharField(max_length=100, default='')
    allergies = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='OTHER')
    medical_history = models.TextField(blank=True, default='')
    is_admitted = models.BooleanField(default=False)
    room_number = models.CharField(max_length=10, blank=True, null=True, default='')
    bed_number = models.CharField(max_length=10, blank=True, null=True, default='')
    admission_date = models.DateTimeField(null=True, blank=True)
    discharge_date = models.DateTimeField(null=True, blank=True)

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

class Doctor(BaseModel):
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
    specialization = models.CharField(max_length=100, choices=SPECIALIZATION_CHOICES, default='GENERAL')
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Enter a valid phone number",
        default=''
    )
    address = models.TextField(default='')
    experience = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Years of experience (0-50)",
        default=0
    )
    qualification = models.CharField(max_length=100, default='')
    is_available = models.BooleanField(default=True)
    emergency_contact = models.CharField(max_length=15, default='')
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    max_patients_per_day = models.IntegerField(default=20)

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

class Appointment(BaseModel):
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show')
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    reason = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_appointments')
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

class MedicalRecord(BaseModel):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='medical_records')
    diagnosis = models.TextField()
    prescription = models.TextField()
    notes = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    is_confidential = models.BooleanField(default=False)

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

class Bill(BaseModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled')
    ]

    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('INSURANCE', 'Insurance'),
        ('ONLINE', 'Online')
    ]

    bill_id = models.UUIDField(unique=True, editable=False, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='bills')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    due_date = models.DateField(default=timezone.now)
    insurance_claim = models.BooleanField(default=False)
    insurance_details = models.TextField(blank=True)
    insurance_provider = models.CharField(max_length=100, blank=True, null=True)
    insurance_policy_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.patient} - ${self.amount}"

    def clean(self):
        if self.paid_amount > self.amount:
            raise ValidationError(_('Paid amount cannot be greater than total amount'))
        
        if self.paid and self.paid_amount < self.amount:
            raise ValidationError(_('Cannot mark as paid when amount is not fully paid'))

    def save(self, *args, **kwargs):
        if not self.bill_id:
            self.bill_id = uuid.uuid4()
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

class Employee(BaseModel):
    POSITION_CHOICES = [
        ('RECEPTIONIST', 'Receptionist'),
        ('NURSE', 'Nurse'),
        ('PHARMACIST', 'Pharmacist'),
        ('TECHNICIAN', 'Lab Technician'),
        ('ADMIN', 'Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Enter a valid phone number",
        default=''
    )
    address = models.TextField(default='')
    position = models.CharField(max_length=50, choices=POSITION_CHOICES, default='RECEPTIONIST')
    department = models.CharField(max_length=100, default='')
    emergency_contact = models.CharField(max_length=15, default='')
    is_active = models.BooleanField(default=True)
    shift = models.CharField(max_length=20, choices=[
        ('MORNING', 'Morning'),
        ('AFTERNOON', 'Afternoon'),
        ('NIGHT', 'Night')
    ], default='MORNING')

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

class InventoryItem(BaseModel):
    CATEGORY_CHOICES = [
        ('MEDICINE', 'Medicine'),
        ('EQUIPMENT', 'Equipment'),
        ('SUPPLIES', 'Supplies')
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField()
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.CharField(max_length=200)
    expiry_date = models.DateField(null=True, blank=True)
    reorder_level = models.IntegerField()
    location = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} - {self.category}"

class LabTest(BaseModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ]

    test_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    technician = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    test_name = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    results = models.TextField(blank=True)
    test_date = models.DateField()
    result_date = models.DateField(null=True, blank=True)
    is_urgent = models.BooleanField(default=False)

    def __str__(self):
        return f"Lab Test: {self.test_name} - {self.patient}"

class Room(BaseModel):
    ROOM_TYPE_CHOICES = [
        ('GENERAL', 'General Ward'),
        ('PRIVATE', 'Private Room'),
        ('SEMI_PRIVATE', 'Semi-Private Room'),
        ('ICU', 'Intensive Care Unit'),
        ('OPERATION', 'Operation Theater')
    ]

    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES)
    capacity = models.IntegerField()
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    floor = models.IntegerField()
    wing = models.CharField(max_length=10)

    def __str__(self):
        return f"Room {self.room_number} - {self.room_type}"

class Bed(BaseModel):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    bed_number = models.CharField(max_length=10)
    is_available = models.BooleanField(default=True)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    admission_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Bed {self.bed_number} - Room {self.room.room_number}"

class EmergencyTeam(BaseModel):
    name = models.CharField(max_length=100)
    leader = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True)
    members = models.ManyToManyField(Employee)
    specialization = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)
    contact_number = models.CharField(max_length=15)

    def __str__(self):
        return f"Emergency Team: {self.name}"

class EmergencyCase(BaseModel):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('RESOLVED', 'Resolved'),
        ('TRANSFERRED', 'Transferred')
    ]

    case_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    team = models.ForeignKey(EmergencyTeam, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    description = models.TextField()
    priority = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    admission_time = models.DateTimeField()
    resolution_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Emergency Case: {self.case_id} - {self.patient}"

class HospitalPolicy(BaseModel):
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    last_reviewed = models.DateField()
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.title

class Notification(BaseModel):
    TYPE_CHOICES = [
        ('APPOINTMENT', 'Appointment'),
        ('BILL', 'Bill'),
        ('EMERGENCY', 'Emergency'),
        ('SYSTEM', 'System')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_read = models.BooleanField(default=False)
    related_object_id = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.user}"
