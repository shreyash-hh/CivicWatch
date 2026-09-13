# CivicWatch

CivicWatch is a modern crowdsourced civic reporting platform. It empowers citizens to report public issues (e.g., potholes, garbage dumps, broken street lights) to local authorities and allows administrators to track and update the status of these reports.

## Features
- **Geo-Tagged Reports:** Submit issues with exact geographic coordinates.
- **Image Compression:** Automatic image resizing and optimization via Pillow.
- **Role-Based Access Control:** Differentiates between regular citizens and civic workers/admins.
- **Status Tracking:** Comprehensive auditing and workflow for tracking the resolution of issues.
- **Dashboard Analytics:** High-level overview of pending vs. resolved issues.

## Setup Instructions

### 1. Requirements
- Python 3.9+
- Django 4.2+ (or newer)

### 2. Installation
First, clone the repository and set up a virtual environment:

```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

Next, install the project dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root `civicwatch/` directory next to `settings.py` and populate it with your local settings:

```env
SECRET_KEY=your_secret_key_here
DEBUG=True
```

### 4. Database Migrations
Run the migrations to set up your SQLite database:
```bash
cd civicwatch
python manage.py makemigrations
python manage.py migrate
```

### 5. Running the Server
Finally, start the Django development server:
```bash
python manage.py runserver
```

Navigate to `http://127.0.0.0:8000/` in your browser.
