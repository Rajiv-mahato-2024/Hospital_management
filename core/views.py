from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from .models import Patient, Doctor, Appointment, MedicalRecord, Bill, Employee, AdminProfile
from datetime import datetime, timedelta, date
import logging
import re

logger = logging.getLogger(__name__)

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

def home(request):
    return render(request, 'core/home.html')

@transaction.atomic
def register(request):
    if request.method == 'POST':
        try:
            # Get and validate basic information
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()
            email = request.POST.get('email', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            user_type = request.POST.get('user_type', '').strip()
            phone = request.POST.get('phone', '').strip()
            address = request.POST.get('address', '').strip()

            # Validate required fields
            if not all([username, password, email, first_name, last_name, user_type, phone, address]):
                messages.error(request, 'All fields are required')
                return render(request, 'core/register.html')

            # Validate email format
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, 'Please enter a valid email address')
                return render(request, 'core/register.html')

            # Validate phone number
            try:
                validate_phone_number(phone)
            except ValidationError as e:
                messages.error(request, str(e))
                return render(request, 'core/register.html')

            # Validate password
            try:
                validate_password(password)
            except ValidationError as e:
                messages.error(request, str(e))
                return render(request, 'core/register.html')

            # Check if username or email already exists
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists')
                return render(request, 'core/register.html')

            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists')
                return render(request, 'core/register.html')

            # Create user
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name
            )

            try:
                # Create profile based on user type
                if user_type == 'patient':
                    date_of_birth = request.POST.get('date_of_birth')
                    blood_group = request.POST.get('blood_group')
                    
                    if not all([date_of_birth, blood_group]):
                        raise ValidationError('Date of birth and blood group are required for patients')

                    # Validate date of birth
                    dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                    if dob >= timezone.now().date():
                        raise ValidationError('Date of birth cannot be in the future')

                    Patient.objects.create(
                        user=user,
                        phone=phone,
                        address=address,
                        date_of_birth=dob,
                        blood_group=blood_group
                    )

                elif user_type == 'doctor':
                    specialization = request.POST.get('specialization')
                    experience = request.POST.get('experience')
                    
                    if not all([specialization, experience]):
                        raise ValidationError('Specialization and experience are required for doctors')

                    # Validate experience
                    try:
                        experience = int(experience)
                        if not (0 <= experience <= 50):
                            raise ValidationError('Experience must be between 0 and 50 years')
                    except ValueError:
                        raise ValidationError('Experience must be a valid number')

                    Doctor.objects.create(
                        user=user,
                        specialization=specialization,
                        phone=phone,
                        address=address,
                        experience=experience
                    )

                elif user_type == 'employee':
                    position = request.POST.get('position')
                    
                    if not position:
                        raise ValidationError('Position is required for employees')

                    Employee.objects.create(
                        user=user,
                        phone=phone,
                        address=address,
                        position=position
                    )

                elif user_type == 'admin':
                    AdminProfile.objects.create(
                        user=user,
                        phone=phone,
                        address=address
                    )
                else:
                    raise ValidationError('Invalid user type')

                login(request, user)
                messages.success(request, 'Registration successful')
                return redirect('dashboard')

            except ValidationError as e:
                user.delete()  # Rollback user creation
                messages.error(request, str(e))
                return render(request, 'core/register.html')

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            messages.error(request, 'An error occurred during registration. Please try again.')
            return render(request, 'core/register.html')

    return render(request, 'core/register.html')

def login_view(request):
    if request.method == 'POST':
        try:
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, 'Login successful')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid credentials')
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            messages.error(request, 'An error occurred during login. Please try again.')

    return render(request, 'core/login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully')
    return redirect('home')

@login_required
def dashboard(request):
    try:
        context = {}
        
        if hasattr(request.user, 'patient'):
            appointments = Appointment.objects.filter(
                patient=request.user.patient,
                appointment_date__gte=timezone.now().date()
            ).order_by('appointment_date', 'appointment_time')
            
            medical_records = MedicalRecord.objects.filter(
                patient=request.user.patient
            ).order_by('-created_at')
            
            bills = Bill.objects.filter(
                patient=request.user.patient
            ).order_by('-created_at')
            
            context.update({
                'appointments': appointments[:5],
                'medical_records': medical_records[:5],
                'bills': bills[:5],
                'total_bills': bills.count(),
                'paid_bills': bills.filter(paid=True).count(),
                'pending_bills': bills.filter(paid=False).count(),
            })
        
        elif hasattr(request.user, 'doctor'):
            today = timezone.now().date()
            appointments = Appointment.objects.filter(
                doctor=request.user.doctor,
                appointment_date=today
            ).order_by('appointment_time')
            
            context.update({
                'today_appointments': appointments,
                'total_patients': Appointment.objects.filter(
                    doctor=request.user.doctor
                ).values('patient').distinct().count(),
                'total_appointments': Appointment.objects.filter(
                    doctor=request.user.doctor
                ).count(),
                'completed_appointments': Appointment.objects.filter(
                    doctor=request.user.doctor,
                    status='COMPLETED'
                ).count(),
            })
        
        elif hasattr(request.user, 'employee'):
            today = timezone.now().date()
            appointments = Appointment.objects.filter(
                appointment_date=today
            ).order_by('appointment_time')
            
            context.update({
                'today_appointments': appointments,
                'total_appointments': Appointment.objects.count(),
                'total_patients': Patient.objects.count(),
                'total_doctors': Doctor.objects.count(),
            })
        
        elif hasattr(request.user, 'adminprofile'):
            context.update({
                'total_patients': Patient.objects.count(),
                'total_doctors': Doctor.objects.count(),
                'total_employees': Employee.objects.count(),
                'total_appointments': Appointment.objects.count(),
                'total_bills': Bill.objects.count(),
                'revenue': Bill.objects.filter(paid=True).aggregate(
                    total=models.Sum('amount')
                )['total'] or 0,
            })
        
        return render(request, 'core/dashboard.html', context)
    
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        messages.error(request, 'An error occurred while loading the dashboard.')
        return redirect('home')

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
        messages.error(request, 'An error occurred while loading the profile.')
        return redirect('dashboard')

@login_required
@user_passes_test(is_patient)
def book_appointment(request):
    try:
        if request.method == 'POST':
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

        doctors = Doctor.objects.filter(is_available=True)
        return render(request, 'core/book_appointment.html', {'doctors': doctors})
    
    except Exception as e:
        logger.error(f"Book appointment error: {str(e)}")
        messages.error(request, 'An error occurred while booking the appointment.')
        return redirect('dashboard')

@login_required
def medical_records(request):
    try:
        if hasattr(request.user, 'patient'):
            records = MedicalRecord.objects.filter(patient=request.user.patient).order_by('-created_at')
        elif hasattr(request.user, 'doctor'):
            records = MedicalRecord.objects.filter(doctor=request.user.doctor).order_by('-created_at')
        else:
            raise PermissionDenied

        return render(request, 'core/medical_records.html', {'records': records})
    
    except Exception as e:
        logger.error(f"Medical records error: {str(e)}")
        messages.error(request, 'An error occurred while loading medical records.')
        return redirect('dashboard')

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
           not (hasattr(request.user, 'patient') and appointment.patient == request.user.patient):
            raise PermissionDenied

        if request.method == 'POST':
            if hasattr(request.user, 'doctor'):
                status = request.POST.get('status')
                notes = request.POST.get('notes')
                
                if status:
                    appointment.status = status
                if notes:
                    appointment.notes = notes
                
                appointment.save()
                messages.success(request, 'Appointment updated successfully')

        return render(request, 'core/appointment_detail.html', {'appointment': appointment})
    
    except Exception as e:
        logger.error(f"Appointment detail error: {str(e)}")
        messages.error(request, 'An error occurred while loading appointment details.')
        return redirect('dashboard')
