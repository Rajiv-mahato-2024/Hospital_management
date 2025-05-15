from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from django.views.decorators.vary import vary_on_cookie
from .models import Patient, Doctor, Appointment, MedicalRecord, Bill, Employee, AdminProfile
from datetime import datetime, timedelta, date
import logging
import re
from .schemas import PatientCreate, DoctorCreate, EmployeeCreate
from .utils import ErrorHandler, DatabaseHandler, SecurityHandler
from functools import wraps
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

logger = logging.getLogger(__name__)

def rate_limit(limit=5, period=60):
    """Rate limiting decorator"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not hasattr(request, 'session'):
                request.session = {}

            now = timezone.now().isoformat()
            key = f'rate_limit_{view_func.__name__}'

            if key in request.session:
                last_time_str, count = request.session[key]
                last_time = datetime.fromisoformat(last_time_str)
                if (datetime.fromisoformat(now) - last_time).seconds < period:
                    if count >= limit:
                        return HttpResponseForbidden('Rate limit exceeded')
                    request.session[key] = (last_time_str, count + 1)
                else:
                    request.session[key] = (now, 1)
            else:
                request.session[key] = (now, 1)

            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator

def is_admin(user):
    return hasattr(user, 'adminprofile')

def is_doctor(user):
    return hasattr(user, 'doctor')

def is_patient(user):
    return hasattr(user, 'patient')

def is_employee(user):
    return hasattr(user, 'employee')

def validate_phone_number(phone):
    if not re.match(r'^[0-9]{10}$', phone):
        raise ValidationError('Phone number must be 10 digits')

def validate_password(password):
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long')
    if not re.search(r'[A-Z]', password):
        raise ValidationError('Password must contain at least one uppercase letter')
    if not re.search(r'[a-z]', password):
        raise ValidationError('Password must contain at least one lowercase letter')
    if not re.search(r'[0-9]', password):
        raise ValidationError('Password must contain at least one number')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError('Password must contain at least one special character')

@csrf_protect
@cache_control(private=True)
@vary_on_cookie
def home(request):
    try:
        return render(request, 'core/home.html')
    except Exception as e:
        logger.error(f"Error in home view: {str(e)}")
        messages.error(request, 'An error occurred. Please try again later.')
        return render(request, 'core/error.html')

@csrf_protect
@rate_limit(limit=5, period=300)  # 5 attempts per 5 minutes
@transaction.atomic
def register(request):
    if request.method == 'POST':
        try:
            # Get user type and prepare data
            user_type = request.POST.get('user_type')
            form_data = {
                'username': request.POST.get('username', '').strip(),
                'email': request.POST.get('email', '').strip(),
                'first_name': request.POST.get('first_name', '').strip(),
                'last_name': request.POST.get('last_name', '').strip(),
                'phone': request.POST.get('phone', '').strip(),
                'address': request.POST.get('address', '').strip(),
                'password': request.POST.get('password', '').strip(),
            }

            # Validate required fields
            is_valid, error_message = ErrorHandler.validate_request_data(
                form_data,
                ['username', 'email', 'first_name', 'last_name', 'phone', 'address', 'password']
            )
            if not is_valid:
                messages.error(request, error_message)
                return render(request, 'core/register.html', {'form_data': request.POST})

            # Validate password strength
            is_strong, password_message = SecurityHandler.validate_password_strength(form_data['password'])
            if not is_strong:
                messages.error(request, password_message)
                return render(request, 'core/register.html', {'form_data': request.POST})

            # Check if username or email already exists
            if User.objects.filter(username=form_data['username']).exists():
                messages.error(request, 'Username already exists')
                return render(request, 'core/register.html', {'form_data': request.POST})

            if User.objects.filter(email=form_data['email']).exists():
                messages.error(request, 'Email already exists')
                return render(request, 'core/register.html', {'form_data': request.POST})

            # Validate data based on user type
            try:
                if user_type == 'patient':
                    form_data.update({
                        'date_of_birth': request.POST.get('date_of_birth'),
                        'blood_group': request.POST.get('blood_group'),
                        'emergency_contact': request.POST.get('emergency_contact', '').strip(),
                        'emergency_contact_name': request.POST.get('emergency_contact_name', '').strip(),
                        'allergies': request.POST.get('allergies', '').strip()
                    })
                    validated_data = PatientCreate(**form_data)
                    
                    # Create user and profile
                    user = DatabaseHandler.safe_db_operation(
                        User.objects.create_user,
                        username=validated_data.username,
                        email=validated_data.email,
                        password=validated_data.password,
                        first_name=validated_data.first_name,
                        last_name=validated_data.last_name
                    )
                    
                    Patient.objects.create(
                        user=user,
                        phone=validated_data.phone,
                        address=validated_data.address,
                        date_of_birth=validated_data.date_of_birth,
                        blood_group=validated_data.blood_group,
                        emergency_contact=validated_data.emergency_contact,
                        emergency_contact_name=validated_data.emergency_contact_name,
                        allergies=validated_data.allergies
                    )

                elif user_type == 'doctor':
                    form_data.update({
                        'specialization': request.POST.get('specialization'),
                        'experience': int(request.POST.get('experience', 0))
                    })
                    validated_data = DoctorCreate(**form_data)
                    
                    user = DatabaseHandler.safe_db_operation(
                        User.objects.create_user,
                        username=validated_data.username,
                        email=validated_data.email,
                        password=validated_data.password,
                        first_name=validated_data.first_name,
                        last_name=validated_data.last_name
                    )
                    
                    Doctor.objects.create(
                        user=user,
                        specialization=validated_data.specialization,
                        phone=validated_data.phone,
                        address=validated_data.address,
                        experience=validated_data.experience
                    )

                elif user_type == 'employee':
                    form_data.update({
                        'position': request.POST.get('position')
                    })
                    validated_data = EmployeeCreate(**form_data)
                    
                    user = DatabaseHandler.safe_db_operation(
                        User.objects.create_user,
                        username=validated_data.username,
                        email=validated_data.email,
                        password=validated_data.password,
                        first_name=validated_data.first_name,
                        last_name=validated_data.last_name
                    )
                    
                    Employee.objects.create(
                        user=user,
                        phone=validated_data.phone,
                        address=validated_data.address,
                        position=validated_data.position
                    )

                elif user_type == 'admin':
                    user = DatabaseHandler.safe_db_operation(
                        User.objects.create_user,
                        username=form_data['username'],
                        email=form_data['email'],
                        password=form_data['password'],
                        first_name=form_data['first_name'],
                        last_name=form_data['last_name']
                    )
                    
                    AdminProfile.objects.create(
                        user=user,
                        phone=form_data['phone'],
                        address=form_data['address']
                    )
                else:
                    raise ValueError('Invalid user type')

                # Log in the user
                login(request, user)
                messages.success(request, 'Registration successful! Welcome to our platform.')
                return redirect('dashboard')

            except Exception as e:
                # If any error occurs during user creation, the transaction will be rolled back
                error_response = ErrorHandler.handle_error(e, 'user_creation')
                messages.error(request, error_response['message'])
                return render(request, 'core/register.html', {'form_data': request.POST})

        except Exception as e:
            error_response = ErrorHandler.handle_error(e, 'registration')
            messages.error(request, error_response['message'])
            return render(request, 'core/register.html', {'form_data': request.POST})

    return render(request, 'core/register.html')

@csrf_protect
@rate_limit(limit=5, period=300)  # 5 attempts per 5 minutes
def login_view(request):
    if request.method == 'POST':
        try:
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()
            
            if not username or not password:
                messages.error(request, 'Please provide both username and password')
                return render(request, 'core/login.html')
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.success(request, 'Login successful!')
                    return redirect('dashboard')
                else:
                    messages.error(request, 'Your account has been disabled. Please contact support.')
            else:
                messages.error(request, 'Invalid username or password')
                
        except Exception as e:
            error_response = ErrorHandler.handle_error(e, 'login')
            messages.error(request, error_response['message'])
            
    return render(request, 'core/login.html')

@login_required
@csrf_protect
def logout_view(request):
    try:
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        messages.error(request, 'An error occurred during logout.')
    return redirect('home')

@login_required
@cache_control(private=True)
@vary_on_cookie
def dashboard(request):
    try:
        context = {}
        today = timezone.now().date()

        if hasattr(request.user, 'patient'):
            # Patient Dashboard
            patient = request.user.patient
            context.update({
                'upcoming_appointments_count': Appointment.objects.filter(
                    patient=patient,
                    appointment_date__gte=today,
                    status='SCHEDULED'
                ).count(),
                'medical_records_count': MedicalRecord.objects.filter(patient=patient).count(),
                'pending_bills_count': Bill.objects.filter(
                    patient=patient,
                    payment_status='PENDING'
                ).count(),
                'total_bills_count': Bill.objects.filter(patient=patient).count(),
                'recent_appointments': Appointment.objects.filter(
                    patient=patient
                ).order_by('-appointment_date', '-appointment_time')[:5]
            })

        elif hasattr(request.user, 'doctor'):
            # Doctor Dashboard
            doctor = request.user.doctor
            context.update({
                'today_appointments_count': Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=today,
                    status='SCHEDULED'
                ).count(),
                'total_patients_count': Patient.objects.filter(
                    appointment__doctor=doctor
                ).distinct().count(),
                'medical_records_count': MedicalRecord.objects.filter(doctor=doctor).count(),
                'today_appointments': Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=today
                ).order_by('appointment_time')
            })

        elif hasattr(request.user, 'employee'):
            # Employee Dashboard
            context.update({
                'today_appointments_count': Appointment.objects.filter(
                    appointment_date=today,
                    status='SCHEDULED'
                ).count(),
                'pending_bills_count': Bill.objects.filter(
                    payment_status='PENDING'
                ).count(),
                'total_patients_count': Patient.objects.count(),
                'total_doctors_count': Doctor.objects.count(),
                'recent_activities': []  # You can implement an activity log system later
            })

        elif hasattr(request.user, 'adminprofile'):
            # Admin Dashboard
            context.update({
                'total_users_count': User.objects.count(),
                'total_doctors_count': Doctor.objects.count(),
                'total_patients_count': Patient.objects.count(),
                'total_employees_count': Employee.objects.count(),
                'total_appointments_count': Appointment.objects.count(),
                'total_medical_records_count': MedicalRecord.objects.count(),
                'total_bills_count': Bill.objects.count(),
                'total_revenue': Bill.objects.filter(
                    payment_status='PAID'
                ).aggregate(total=Sum('amount'))['total'] or 0
            })

        return render(request, 'core/dashboard.html', context)

    except Exception as e:
        return render(request, 'core/error.html', {
            'error_title': 'Dashboard Error',
            'error_message': 'An error occurred while loading the dashboard.',
            'error_details': str(e)
        })

@login_required
def profile_view(request):
    try:
        user = request.user
        profile = None
        
        if hasattr(user, 'patient'):
            profile = user.patient
        elif hasattr(user, 'doctor'):
            profile = user.doctor
        elif hasattr(user, 'employee'):
            profile = user.employee
        elif hasattr(user, 'adminprofile'):
            profile = user.adminprofile

        if request.method == 'POST':
            try:
                # Update user information
                user.first_name = request.POST.get('first_name')
                user.last_name = request.POST.get('last_name')
                user.email = request.POST.get('email')
                user.save()

                # Update profile information
                if profile:
                    profile.phone = request.POST.get('phone')
                    profile.address = request.POST.get('address')

                    if hasattr(user, 'doctor'):
                        profile.specialization = request.POST.get('specialization')
                        profile.experience = request.POST.get('experience')
                    elif hasattr(user, 'employee'):
                        profile.position = request.POST.get('position')

                    profile.save()
                
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
            except Exception as e:
                logger.error(f"Profile update error: {str(e)}")
                messages.error(request, 'Failed to update profile. Please try again.')
                return render(request, 'core/error.html', {
                    'error_title': 'Profile Update Error',
                    'error_message': 'Failed to update profile information.',
                    'error_details': str(e)
                })

        context = {
            'user': user,
            'profile': profile,
        }

        # Add appointments for patients
        if hasattr(user, 'patient'):
            context['appointments'] = user.patient.appointment_set.filter(
                appointment_date__gte=timezone.now().date()
            ).order_by('appointment_date', 'appointment_time')
            context['medical_records'] = user.patient.medicalrecord_set.all().order_by('-created_at')

        # Add today's appointments for doctors
        if hasattr(user, 'doctor'):
            context['appointments'] = user.doctor.appointment_set.filter(
                appointment_date=timezone.now().date()
            ).order_by('appointment_time')

        return render(request, 'core/profile.html', context)
    
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return render(request, 'core/error.html', {
            'error_title': 'Profile Error',
            'error_message': 'An error occurred while loading the profile.',
            'error_details': str(e)
        })

@login_required
@user_passes_test(is_patient)
def book_appointment(request):
    try:
        if request.method == 'POST':
            try:
                doctor = get_object_or_404(Doctor, id=request.POST['doctor'])
                appointment_date = request.POST['appointment_date']
                appointment_time = request.POST['appointment_time']
                reason = request.POST['reason']

                # Validate appointment date
                if datetime.strptime(appointment_date, '%Y-%m-%d').date() < timezone.now().date():
                    messages.error(request, 'Cannot book appointments for past dates')
                    return redirect('book_appointment')

                # Check if doctor is available
                if not doctor.is_available:
                    messages.error(request, 'Doctor is not available at the moment')
                    return redirect('book_appointment')

                # Check if time slot is available
                if Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    status__in=['PENDING', 'CONFIRMED']
                ).exists():
                    messages.error(request, 'This time slot is already booked')
                    return redirect('book_appointment')

                Appointment.objects.create(
                    patient=request.user.patient,
                    doctor=doctor,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    reason=reason
                )

                messages.success(request, 'Appointment booked successfully')
                return redirect('dashboard')
            except Exception as e:
                logger.error(f"Appointment booking error: {str(e)}")
                return render(request, 'core/error.html', {
                    'error_title': 'Booking Error',
                    'error_message': 'Failed to book appointment.',
                    'error_details': str(e)
                })

        doctors = Doctor.objects.filter(is_available=True)
        return render(request, 'core/book_appointment.html', {'doctors': doctors})
    
    except Exception as e:
        logger.error(f"Book appointment error: {str(e)}")
        return render(request, 'core/error.html', {
            'error_title': 'Appointment Error',
            'error_message': 'An error occurred while accessing the booking page.',
            'error_details': str(e)
        })

@login_required
def medical_records(request):
    try:
        if hasattr(request.user, 'patient'):
            records = MedicalRecord.objects.filter(patient=request.user.patient).order_by('-created_at')
            context = {
                'records': records,
                'is_patient': True
            }
        elif hasattr(request.user, 'doctor'):
            records = MedicalRecord.objects.filter(doctor=request.user.doctor).order_by('-created_at')
            context = {
                'records': records,
                'is_doctor': True
            }
        else:
            return render(request, 'core/error.html', {
                'error_title': 'Access Denied',
                'error_message': 'You do not have permission to view medical records.',
                'error_details': 'Only patients and doctors can access medical records.'
            })

        return render(request, 'core/medical_records.html', context)
    
    except Exception as e:
        logger.error(f"Medical records error: {str(e)}")
        return render(request, 'core/error.html', {
            'error_title': 'Medical Records Error',
            'error_message': 'An error occurred while loading medical records.',
            'error_details': str(e)
        })

@login_required
@user_passes_test(is_doctor)
def appointments(request):
    try:
        appointments = Appointment.objects.filter(
            doctor=request.user.doctor
        ).order_by('appointment_date', 'appointment_time')
        
        return render(request, 'core/appointments.html', {'appointments': appointments})
    
    except Exception as e:
        logger.error(f"Appointments error: {str(e)}")
        messages.error(request, 'An error occurred while loading appointments.')
        return redirect('dashboard')

@login_required
@user_passes_test(is_doctor)
def patients(request):
    try:
        patients = Patient.objects.filter(
            appointment__doctor=request.user.doctor
        ).distinct()
        
        return render(request, 'core/patients.html', {'patients': patients})
    
    except Exception as e:
        logger.error(f"Patients error: {str(e)}")
        messages.error(request, 'An error occurred while loading patients.')
        return redirect('dashboard')

@login_required
@user_passes_test(is_doctor)
def patient_detail(request, patient_id):
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        medical_records = MedicalRecord.objects.filter(
            patient=patient,
            doctor=request.user.doctor
        )
        appointments = Appointment.objects.filter(
            patient=patient,
            doctor=request.user.doctor
        )

        if request.method == 'POST':
            MedicalRecord.objects.create(
                patient=patient,
                doctor=request.user.doctor,
                diagnosis=request.POST['diagnosis'],
                prescription=request.POST['prescription'],
                notes=request.POST['notes'],
                follow_up_date=request.POST.get('follow_up_date')
            )
            messages.success(request, 'Medical record added successfully')
            return redirect('patient_detail', patient_id=patient_id)

        return render(request, 'core/patient_detail.html', {
            'patient': patient,
            'medical_records': medical_records,
            'appointments': appointments
        })
    
    except Exception as e:
        logger.error(f"Patient detail error: {str(e)}")
        messages.error(request, 'An error occurred while loading patient details.')
        return redirect('patients')

@login_required
def appointment_detail(request, appointment_id):
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        # Check if user has permission to view this appointment
        if not (hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor) and \
           not (hasattr(request.user, 'patient') and appointment.patient == request.user.patient) and \
           not (hasattr(request.user, 'employee') or hasattr(request.user, 'adminprofile')):
            return render(request, 'core/error.html', {
                'error_title': 'Access Denied',
                'error_message': 'You do not have permission to view this appointment.',
                'error_details': 'Only the patient, doctor, or staff members can view appointment details.'
            })

        if request.method == 'POST':
            try:
                if hasattr(request.user, 'doctor'):
                    status = request.POST.get('status')
                    notes = request.POST.get('notes')
                    
                    if status and status not in dict(Appointment.STATUS_CHOICES):
                        raise ValidationError('Invalid appointment status')
                    
                    if status:
                        appointment.status = status
                    if notes:
                        appointment.notes = notes
                    
                    appointment.save()
                    messages.success(request, 'Appointment updated successfully')
                elif hasattr(request.user, 'employee') or hasattr(request.user, 'adminprofile'):
                    status = request.POST.get('status')
                    if status and status not in dict(Appointment.STATUS_CHOICES):
                        raise ValidationError('Invalid appointment status')
                    
                    appointment.status = status
                    appointment.save()
                    messages.success(request, 'Appointment status updated successfully')
                else:
                    return render(request, 'core/error.html', {
                        'error_title': 'Permission Denied',
                        'error_message': 'You do not have permission to update this appointment.',
                        'error_details': 'Only doctors and staff members can update appointments.'
                    })
            except ValidationError as e:
                return render(request, 'core/error.html', {
                    'error_title': 'Validation Error',
                    'error_message': 'Invalid appointment data.',
                    'error_details': str(e)
                })
            except Exception as e:
                logger.error(f"Appointment update error: {str(e)}")
                return render(request, 'core/error.html', {
                    'error_title': 'Update Error',
                    'error_message': 'Failed to update appointment.',
                    'error_details': str(e)
                })

        context = {
            'appointment': appointment,
            'is_doctor': hasattr(request.user, 'doctor'),
            'is_patient': hasattr(request.user, 'patient'),
            'is_staff': hasattr(request.user, 'employee') or hasattr(request.user, 'adminprofile')
        }
        return render(request, 'core/appointment_detail.html', context)
    
    except Appointment.DoesNotExist:
        return render(request, 'core/error.html', {
            'error_title': 'Not Found',
            'error_message': 'The requested appointment does not exist.',
            'error_details': 'The appointment may have been deleted or you may have entered an invalid ID.'
        })
    except Exception as e:
        logger.error(f"Appointment detail error: {str(e)}")
        return render(request, 'core/error.html', {
            'error_title': 'Appointment Error',
            'error_message': 'An error occurred while loading appointment details.',
            'error_details': str(e)
        })

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    try:
        # Get date range for analytics
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

        context = {
            # Basic Statistics
            'total_patients': Patient.objects.count(),
            'total_doctors': Doctor.objects.count(),
            'total_employees': Employee.objects.count(),
            'total_appointments': Appointment.objects.count(),
            'total_bills': Bill.objects.count(),
            'revenue': Bill.objects.filter(payment_status='PAID').aggregate(
                total=Sum('amount')
            )['total'] or 0,

            # Recent Activity
            'recent_appointments': Appointment.objects.all().order_by('-created_at')[:5],
            'recent_bills': Bill.objects.all().order_by('-created_at')[:5],

            # Analytics Data
            'patient_stats': {
                'new_patients': Patient.objects.filter(
                    user__date_joined__date__range=[start_date, end_date]
                ).count(),
                'active_patients': Patient.objects.filter(
                    appointment__appointment_date__range=[start_date, end_date]
                ).distinct().count(),
            },
            'appointment_stats': {
                'scheduled': Appointment.objects.filter(
                    appointment_date__range=[start_date, end_date],
                    status='SCHEDULED'
                ).count(),
                'completed': Appointment.objects.filter(
                    appointment_date__range=[start_date, end_date],
                    status='COMPLETED'
                ).count(),
                'cancelled': Appointment.objects.filter(
                    appointment_date__range=[start_date, end_date],
                    status='CANCELLED'
                ).count(),
            },
            'revenue_stats': {
                'total': Bill.objects.filter(
                    created_at__date__range=[start_date, end_date],
                    payment_status='PAID'
                ).aggregate(total=Sum('amount'))['total'] or 0,
                'pending': Bill.objects.filter(
                    created_at__date__range=[start_date, end_date],
                    payment_status='PENDING'
                ).aggregate(total=Sum('amount'))['total'] or 0,
            },
            'staff_stats': {
                'doctors': Doctor.objects.filter(is_available=True).count(),
                'nurses': Employee.objects.filter(position='NURSE').count(),
                'technicians': Employee.objects.filter(position='TECHNICIAN').count(),
            },
        }

        return render(request, 'core/admin/dashboard.html', context)
    except Exception as e:
        logger.error(f"Admin dashboard error: {str(e)}")
        messages.error(request, 'An error occurred while loading the admin dashboard.')
        return redirect('home')

@login_required
@user_passes_test(is_admin)
def manage_doctors(request):
    try:
        doctors = Doctor.objects.all().select_related('user')
        context = {
            'doctors': doctors,
            'title': 'Manage Doctors'
        }
        return render(request, 'core/admin/manage_doctors.html', context)
    except Exception as e:
        logger.error(f"Error in manage_doctors: {str(e)}")
        messages.error(request, 'An error occurred while loading doctors.')
        return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def manage_employees(request):
    try:
        employees = Employee.objects.all().select_related('user')
        context = {
            'employees': employees,
            'title': 'Manage Staff'
        }
        return render(request, 'core/admin/manage_employees.html', context)
    except Exception as e:
        logger.error(f"Error in manage_employees: {str(e)}")
        messages.error(request, 'An error occurred while loading staff.')
        return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def manage_patients(request):
    try:
        patients = Patient.objects.all().select_related('user')
        context = {
            'patients': patients,
            'title': 'Manage Patients'
        }
        return render(request, 'core/admin/manage_patients.html', context)
    except Exception as e:
        logger.error(f"Error in manage_patients: {str(e)}")
        messages.error(request, 'An error occurred while loading patients.')
        return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def manage_admins(request):
    try:
        admins = User.objects.filter(is_staff=True).exclude(id=request.user.id)
        context = {
            'admins': admins,
            'title': 'Manage Administrators'
        }
        return render(request, 'core/admin/manage_admins.html', context)
    except Exception as e:
        logger.error(f"Error in manage_admins: {str(e)}")
        messages.error(request, 'An error occurred while loading administrators.')
        return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def create_user(request, user_type):
    try:
        if request.method == 'POST':
            form = UserCreationForm(request.POST)
            if form.is_valid():
                user = form.save()
                
                if user_type == 'doctor':
                    Doctor.objects.create(
                        user=user,
                        specialization=request.POST.get('specialization'),
                        experience=request.POST.get('experience'),
                        qualification=request.POST.get('qualification'),
                        phone_number=request.POST.get('phone_number'),
                        emergency_contact=request.POST.get('emergency_contact'),
                        consultation_fee=request.POST.get('consultation_fee')
                    )
                elif user_type == 'employee':
                    Employee.objects.create(
                        user=user,
                        position=request.POST.get('position'),
                        department=request.POST.get('department'),
                        phone_number=request.POST.get('phone_number'),
                        emergency_contact=request.POST.get('emergency_contact'),
                        shift=request.POST.get('shift')
                    )
                elif user_type == 'patient':
                    Patient.objects.create(
                        user=user,
                        date_of_birth=request.POST.get('date_of_birth'),
                        gender=request.POST.get('gender'),
                        blood_group=request.POST.get('blood_group'),
                        address=request.POST.get('address'),
                        phone_number=request.POST.get('phone_number'),
                        emergency_contact=request.POST.get('emergency_contact')
                    )
                elif user_type == 'admin':
                    user.is_staff = True
                    user.save()

                messages.success(request, f'{user_type.title()} created successfully.')
                return redirect(f'manage_{user_type}s')
        else:
            form = UserCreationForm()

        context = {
            'form': form,
            'user_type': user_type,
            'title': f'Create {user_type.title()}'
        }
        return render(request, 'core/admin/create_user.html', context)
    except Exception as e:
        logger.error(f"Error in create_user: {str(e)}")
        messages.error(request, f'An error occurred while creating {user_type}.')
        return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def edit_user(request, user_type, user_id):
    try:
        user = User.objects.get(id=user_id)
        if request.method == 'POST':
            form = UserChangeForm(request.POST, instance=user)
            if form.is_valid():
                user = form.save()
                
                if user_type == 'doctor':
                    doctor = Doctor.objects.get(user=user)
                    doctor.specialization = request.POST.get('specialization')
                    doctor.experience = request.POST.get('experience')
                    doctor.qualification = request.POST.get('qualification')
                    doctor.phone_number = request.POST.get('phone_number')
                    doctor.emergency_contact = request.POST.get('emergency_contact')
                    doctor.consultation_fee = request.POST.get('consultation_fee')
                    doctor.save()
                elif user_type == 'employee':
                    employee = Employee.objects.get(user=user)
                    employee.position = request.POST.get('position')
                    employee.department = request.POST.get('department')
                    employee.phone_number = request.POST.get('phone_number')
                    employee.emergency_contact = request.POST.get('emergency_contact')
                    employee.shift = request.POST.get('shift')
                    employee.save()
                elif user_type == 'patient':
                    patient = Patient.objects.get(user=user)
                    patient.date_of_birth = request.POST.get('date_of_birth')
                    patient.gender = request.POST.get('gender')
                    patient.blood_group = request.POST.get('blood_group')
                    patient.address = request.POST.get('address')
                    patient.phone_number = request.POST.get('phone_number')
                    patient.emergency_contact = request.POST.get('emergency_contact')
                    patient.save()
                elif user_type == 'admin':
                    user.is_staff = True
                    user.save()

                messages.success(request, f'{user_type.title()} updated successfully.')
                return redirect(f'manage_{user_type}s')
        else:
            form = UserChangeForm(instance=user)

        context = {
            'form': form,
            'user_type': user_type,
            'user': user,
            'title': f'Edit {user_type.title()}'
        }
        return render(request, 'core/admin/edit_user.html', context)
    except User.DoesNotExist:
        messages.error(request, f'{user_type.title()} not found.')
        return redirect('admin_dashboard')
    except Exception as e:
        logger.error(f"Error in edit_user: {str(e)}")
        messages.error(request, f'An error occurred while editing {user_type}.')
        return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_type, user_id):
    try:
        user = User.objects.get(id=user_id)
        if request.method == 'POST':
            user.delete()
            messages.success(request, f'{user_type.title()} deleted successfully.')
            return redirect(f'manage_{user_type}s')
        
        context = {
            'user_type': user_type,
            'user': user,
            'title': f'Delete {user_type.title()}'
        }
        return render(request, 'core/admin/delete_user.html', context)
    except User.DoesNotExist:
        messages.error(request, f'{user_type.title()} not found.')
        return redirect('admin_dashboard')
    except Exception as e:
        logger.error(f"Error in delete_user: {str(e)}")
        messages.error(request, f'An error occurred while deleting {user_type}.')
        return redirect('admin_dashboard')

@login_required
@user_passes_test(is_employee)
def employee_dashboard(request):
    try:
        today = timezone.now().date()
        context = {
            'today_appointments': Appointment.objects.filter(
                appointment_date=today
            ).order_by('appointment_time'),
            'total_appointments': Appointment.objects.count(),
            'total_patients': Patient.objects.count(),
            'total_doctors': Doctor.objects.count(),
            'pending_bills': Bill.objects.filter(paid=False).count(),
            'total_revenue': Bill.objects.filter(paid=True).aggregate(
                total=Sum('amount')
            )['total'] or 0,
        }
        return render(request, 'core/employee/dashboard.html', context)
    except Exception as e:
        logger.error(f"Employee dashboard error: {str(e)}")
        messages.error(request, 'An error occurred while loading the employee dashboard.')
        return redirect('home')

@login_required
@user_passes_test(is_employee)
def manage_appointments_employee(request):
    try:
        appointments = Appointment.objects.all().select_related('patient', 'doctor')
        if request.method == 'POST':
            appointment_id = request.POST.get('appointment_id')
            action = request.POST.get('action')
            appointment = get_object_or_404(Appointment, id=appointment_id)
            
            if action == 'confirm':
                appointment.status = 'CONFIRMED'
                appointment.save()
                messages.success(request, 'Appointment confirmed successfully')
            elif action == 'cancel':
                appointment.status = 'CANCELLED'
                appointment.save()
                messages.success(request, 'Appointment cancelled successfully')
            elif action == 'complete':
                appointment.status = 'COMPLETED'
                appointment.save()
                messages.success(request, 'Appointment marked as completed')
            
            return redirect('manage_appointments_employee')
        
        return render(request, 'core/employee/manage_appointments.html', {'appointments': appointments})
    except Exception as e:
        logger.error(f"Manage appointments error: {str(e)}")
        messages.error(request, 'An error occurred while managing appointments.')
        return redirect('employee_dashboard')

@login_required
@user_passes_test(is_employee)
def manage_bills_employee(request):
    try:
        bills = Bill.objects.all().select_related('patient')
        if request.method == 'POST':
            bill_id = request.POST.get('bill_id')
            action = request.POST.get('action')
            bill = get_object_or_404(Bill, id=bill_id)
            
            if action == 'mark_paid':
                bill.paid = True
                bill.save()
                messages.success(request, 'Bill marked as paid successfully')
            elif action == 'delete':
                bill.delete()
                messages.success(request, 'Bill deleted successfully')
            
            return redirect('manage_bills_employee')
        
        return render(request, 'core/employee/manage_bills.html', {'bills': bills})
    except Exception as e:
        logger.error(f"Manage bills error: {str(e)}")
        messages.error(request, 'An error occurred while managing bills.')
        return redirect('employee_dashboard')

@login_required
@user_passes_test(is_employee)
def create_bill(request):
    try:
        if request.method == 'POST':
            patient_id = request.POST.get('patient')
            amount = request.POST.get('amount')
            description = request.POST.get('description')
            
            patient = get_object_or_404(Patient, id=patient_id)
            
            Bill.objects.create(
                patient=patient,
                amount=amount,
                description=description,
                created_by=request.user
            )
            
            messages.success(request, 'Bill created successfully')
            return redirect('manage_bills_employee')
        
        patients = Patient.objects.all()
        return render(request, 'core/employee/create_bill.html', {'patients': patients})
    except Exception as e:
        logger.error(f"Create bill error: {str(e)}")
        messages.error(request, 'An error occurred while creating the bill.')
        return redirect('manage_bills_employee')

@login_required
@user_passes_test(is_employee)
def patient_records(request):
    try:
        patients = Patient.objects.all().select_related('user')
        return render(request, 'core/employee/patient_records.html', {'patients': patients})
    except Exception as e:
        logger.error(f"Patient records error: {str(e)}")
        messages.error(request, 'An error occurred while loading patient records.')
        return redirect('employee_dashboard')

@login_required
@user_passes_test(is_employee)
def doctor_schedule(request):
    try:
        doctors = Doctor.objects.filter(is_available=True).select_related('user')
        return render(request, 'core/employee/doctor_schedule.html', {'doctors': doctors})
    except Exception as e:
        logger.error(f"Doctor schedule error: {str(e)}")
        messages.error(request, 'An error occurred while loading doctor schedules.')
        return redirect('employee_dashboard')
