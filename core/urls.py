from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Patient URLs
    path('book-appointment/', views.book_appointment, name='book_appointment'),
    path('medical-records/', views.medical_records, name='medical_records'),
    
    # Doctor URLs
    path('appointments/', views.appointments, name='appointments'),
    path('patients/', views.patients, name='patients'),
    path('patient/<int:patient_id>/', views.patient_detail, name='patient_detail'),
    path('appointment/<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),
    
    # Admin URLs
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/doctors/', views.manage_doctors, name='manage_doctors'),
    path('admin/employees/', views.manage_employees, name='manage_employees'),
    path('admin/patients/', views.manage_patients, name='manage_patients'),
    path('admin/admins/', views.manage_admins, name='manage_admins'),
    
    # Employee URLs
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/appointments/', views.manage_appointments_employee, name='manage_appointments_employee'),
    path('employee/bills/', views.manage_bills_employee, name='manage_bills_employee'),
    path('employee/create-bill/', views.create_bill, name='create_bill'),
    path('employee/patients/', views.patient_records, name='patient_records'),
    path('employee/doctors/', views.doctor_schedule, name='doctor_schedule'),
] 