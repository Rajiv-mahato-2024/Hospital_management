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
] 