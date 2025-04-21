from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Patient, Doctor, Appointment, MedicalRecord, Bill
from datetime import datetime, timedelta, date

def home(request):
    return render(request, 'core/home.html')

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        user_type = request.POST['user_type']

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return redirect('register')

        user = User.objects.create_user(username=username, password=password, email=email,
                                      first_name=first_name, last_name=last_name)

        if user_type == 'patient':
            Patient.objects.create(
                user=user,
                phone=request.POST['phone'],
                address=request.POST['address'],
                date_of_birth=request.POST['date_of_birth'],
                blood_group=request.POST['blood_group']
            )
        elif user_type == 'doctor':
            Doctor.objects.create(
                user=user,
                specialization=request.POST['specialization'],
                phone=request.POST['phone'],
                address=request.POST['address'],
                experience=request.POST['experience']
            )

        login(request, user)
        messages.success(request, 'Registration successful')
        return redirect('dashboard')

    return render(request, 'core/register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')

    return render(request, 'core/login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully')
    return redirect('home')

@login_required
def dashboard(request):
    context = {}
    
    if hasattr(request.user, 'patient'):
        appointments = Appointment.objects.filter(patient=request.user.patient).order_by('-appointment_date')
        medical_records = MedicalRecord.objects.filter(patient=request.user.patient).order_by('-created_at')
        bills = Bill.objects.filter(patient=request.user.patient).order_by('-created_at')
        
        context.update({
            'appointments': appointments[:5],
            'medical_records': medical_records[:5],
            'bills': bills[:5],
        })
    
    elif hasattr(request.user, 'doctor'):
        today = datetime.now().date()
        appointments = Appointment.objects.filter(
            doctor=request.user.doctor,
            appointment_date=today
        ).order_by('appointment_time')
        
        context.update({
            'today_appointments': appointments,
            'total_patients': Appointment.objects.filter(doctor=request.user.doctor).values('patient').distinct().count(),
        })
    
    return render(request, 'core/dashboard.html', context)

@login_required
def profile_view(request):
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        # Update user information
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()

        # Update profile information
        profile.phone = request.POST.get('phone')
        profile.address = request.POST.get('address')

        if user.is_doctor:
            profile.specialization = request.POST.get('specialization')
            profile.experience = request.POST.get('experience')

        profile.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')

    context = {
        'user': user,
        'profile': profile,
    }

    # Add appointments for patients
    if user.is_patient:
        context['appointments'] = user.patient.appointment_set.filter(
            date__gte=date.today()
        ).order_by('date', 'time')
        context['medical_records'] = user.patient.medicalrecord_set.all().order_by('-date')

    # Add today's appointments for doctors
    if user.is_doctor:
        context['appointments'] = user.doctor.appointment_set.filter(
            date=date.today()
        ).order_by('time')

    return render(request, 'core/profile.html', context)

@login_required
def book_appointment(request):
    if not hasattr(request.user, 'patient'):
        messages.error(request, 'Only patients can book appointments')
        return redirect('dashboard')

    if request.method == 'POST':
        doctor = get_object_or_404(Doctor, id=request.POST['doctor'])
        appointment_date = request.POST['appointment_date']
        appointment_time = request.POST['appointment_time']
        reason = request.POST['reason']

        Appointment.objects.create(
            patient=request.user.patient,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason
        )

        messages.success(request, 'Appointment booked successfully')
        return redirect('dashboard')

    doctors = Doctor.objects.all()
    return render(request, 'core/book_appointment.html', {'doctors': doctors})

@login_required
def medical_records(request):
    if hasattr(request.user, 'patient'):
        records = MedicalRecord.objects.filter(patient=request.user.patient).order_by('-created_at')
    elif hasattr(request.user, 'doctor'):
        records = MedicalRecord.objects.filter(doctor=request.user.doctor).order_by('-created_at')
    else:
        messages.error(request, 'Unauthorized access')
        return redirect('dashboard')

    return render(request, 'core/medical_records.html', {'records': records})

@login_required
def appointments(request):
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Only doctors can view appointments')
        return redirect('dashboard')

    appointments = Appointment.objects.filter(doctor=request.user.doctor).order_by('appointment_date', 'appointment_time')
    return render(request, 'core/appointments.html', {'appointments': appointments})

@login_required
def patients(request):
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Only doctors can view patients')
        return redirect('dashboard')

    patients = Patient.objects.filter(
        appointment__doctor=request.user.doctor
    ).distinct()
    return render(request, 'core/patients.html', {'patients': patients})

@login_required
def patient_detail(request, patient_id):
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Only doctors can view patient details')
        return redirect('dashboard')

    patient = get_object_or_404(Patient, id=patient_id)
    medical_records = MedicalRecord.objects.filter(patient=patient, doctor=request.user.doctor)
    appointments = Appointment.objects.filter(patient=patient, doctor=request.user.doctor)

    if request.method == 'POST':
        MedicalRecord.objects.create(
            patient=patient,
            doctor=request.user.doctor,
            diagnosis=request.POST['diagnosis'],
            prescription=request.POST['prescription'],
            notes=request.POST['notes']
        )
        messages.success(request, 'Medical record added successfully')
        return redirect('patient_detail', patient_id=patient_id)

    return render(request, 'core/patient_detail.html', {
        'patient': patient,
        'medical_records': medical_records,
        'appointments': appointments
    })

@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    if not (hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor) and \
       not (hasattr(request.user, 'patient') and appointment.patient == request.user.patient):
        messages.error(request, 'Unauthorized access')
        return redirect('dashboard')

    if request.method == 'POST':
        if hasattr(request.user, 'doctor'):
            status = request.POST.get('status')
            if status:
                appointment.status = status
                appointment.save()
                messages.success(request, 'Appointment status updated successfully')

    return render(request, 'core/appointment_detail.html', {'appointment': appointment})
