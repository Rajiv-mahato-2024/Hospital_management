from django.contrib import admin
from .models import Patient, Doctor, Appointment, MedicalRecord, Bill

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'blood_group', 'date_of_birth', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')
    list_filter = ('blood_group', 'created_at')

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'experience', 'phone', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'specialization')
    list_filter = ('specialization', 'experience', 'created_at')

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'appointment_date', 'appointment_time', 'status', 'created_at')
    search_fields = ('patient__user__username', 'doctor__user__username', 'reason')
    list_filter = ('status', 'appointment_date', 'created_at')

@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'created_at')
    search_fields = ('patient__user__username', 'doctor__user__username', 'diagnosis', 'prescription')
    list_filter = ('created_at',)

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('patient', 'amount', 'paid', 'payment_date', 'created_at')
    search_fields = ('patient__user__username',)
    list_filter = ('paid', 'created_at')
