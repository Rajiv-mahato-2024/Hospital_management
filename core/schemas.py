from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import date, datetime
import re

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., min_length=10, max_length=15)
    address: str = Field(..., min_length=5, max_length=200)

    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^[0-9]{10}$', v):
            raise ValueError('Phone number must be 10 digits')
        return v

class PatientCreate(UserBase):
    date_of_birth: date
    blood_group: str = Field(..., min_length=2, max_length=5)
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

class DoctorCreate(UserBase):
    specialization: str = Field(..., min_length=2, max_length=100)
    experience: int = Field(..., ge=0, le=50)
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

class EmployeeCreate(UserBase):
    position: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_date: date
    appointment_time: str
    reason: str = Field(..., min_length=10, max_length=500)

    @validator('appointment_date')
    def validate_appointment_date(cls, v):
        if v < date.today():
            raise ValueError('Appointment date cannot be in the past')
        return v

    @validator('appointment_time')
    def validate_appointment_time(cls, v):
        try:
            datetime.strptime(v, '%H:%M')
        except ValueError:
            raise ValueError('Invalid time format. Use HH:MM')
        return v

class MedicalRecordCreate(BaseModel):
    patient_id: int
    doctor_id: int
    diagnosis: str = Field(..., min_length=10, max_length=1000)
    prescription: str = Field(..., min_length=10, max_length=1000)
    notes: Optional[str] = Field(None, max_length=1000)
    follow_up_date: Optional[date] = None

class BillCreate(BaseModel):
    patient_id: int
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=10, max_length=500)

class FileUpload(BaseModel):
    file_name: str
    file_type: str
    file_size: int

    @validator('file_type')
    def validate_file_type(cls, v):
        allowed_types = ['image/jpeg', 'image/png', 'application/pdf']
        if v not in allowed_types:
            raise ValueError(f'File type must be one of {allowed_types}')
        return v

    @validator('file_size')
    def validate_file_size(cls, v):
        max_size = 5 * 1024 * 1024  # 5MB
        if v > max_size:
            raise ValueError('File size must be less than 5MB')
        return v 