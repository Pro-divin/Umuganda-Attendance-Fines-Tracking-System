# Umuganda-Attendance-Fines-Tracking-System-UATS-
digital community attendance
Umuganda-Attendance-Fines-Tracking-System-UATS-
digital community attendance

Umuganda Attendance Tracking System (UATS)
A Django-based web application for managing community work (Umuganda) attendance records, fines, and reporting.

Installation & Setup

Prerequisites
Python 3.8 or higher
pip (Python package manager)
Git (for version control)
Set Up Virtual Environment bash
Create virtual environment
python -m venv venv

Activate virtual environment (Windows)
.\venv\Scripts\activate

For Linux/MacOS
source venv/bin/activate 3. Install Django and Dependencies bash

Install Django
pip install django

Install additional requirements (if you have requirements.txt)
pip install -r requirements.txt 4. Set Up the Project bash

Clone the repository
git clone https://github.com/Pro-divin/Umuganda-Attendance-Fines-Tracking-System-UATS-.git cd Umuganda-Attendance-Fines-Tracking-System-UATS-

Create database tables
python manage.py migrate

Create superuser (admin account)
python manage.py createsuperuser 5. Run Development Server bash python manage.py runserver Access the application at: http://127.0.0.1:8000/

Project Structure text uats_project/ ├── manage.py # Django command-line utility ├── uats/ # Main application directory │ ├── migrations/ # Database migration files │ ├── templates/ # HTML templates │ ├── admin.py # Admin configuration │ ├── apps.py # App configuration │ ├── models.py # Data models │ ├── urls.py # App URL routing │ └── views.py # View functions └── uats_project/ # Project settings ├── settings.py # Project configuration ├── urls.py # Main URL routing └── wsgi.py # WSGI configuration

admin username and password
admin :

username: divin2250@gmail.com password : TestPass123

citizen user account:
username : yvan password: Abcde123.

local leader account:
username: Mudugudu password : Abcde123.

sector account
username : kiki password : Abcde123.#   U m u g a n d a - A t t e n d a n c e - F i n e s - T r a c k i n g - S y s t e m - U A T S  
 