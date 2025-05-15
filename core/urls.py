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
    path('doctors/', views.doctor_profiles, name='doctor_profiles'),
    path('doctors/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'),
    
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
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/<int:employee_id>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:employee_id>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:employee_id>/delete/', views.employee_delete, name='employee_delete'),
    
    # Appointment URLs
    path('appointments/book/', views.book_appointment, name='book_appointment'),
    
    # Patient URLs
    path('patients/search/', views.patient_search, name='patient_search'),
    path('patients/<int:patient_id>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:patient_id>/bills/', views.patient_bills, name='patient_bills'),
    path('patients/<int:patient_id>/reports/', views.patient_reports, name='patient_reports'),
] 