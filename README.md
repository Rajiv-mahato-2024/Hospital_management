# Hospital Management System

A modern web-based hospital management system built with Django and Tailwind CSS.

## Features

- User Authentication (Doctors and Patients)
- Appointment Management
- Medical Records Management
- Patient Management
- Billing System
- Modern UI with Tailwind CSS

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/hospital_management.git
cd hospital_management
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Apply database migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Create a superuser (admin):
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

7. Visit http://127.0.0.1:8000 in your web browser

## Usage

1. Register as either a patient or doctor
2. Log in to access your dashboard
3. Patients can:
   - Book appointments
   - View medical records
   - View bills
4. Doctors can:
   - View appointments
   - Manage patients
   - Create medical records

## Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.
