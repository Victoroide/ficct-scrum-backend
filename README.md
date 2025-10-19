# FICCT-SCRUM Backend API

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0.7-green.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15-orange.svg)](https://www.django-rest-framework.org/)

A production-ready Django REST Framework backend for agile project management, supporting organizations, workspaces, projects, and comprehensive logging.

---

## 🚀 Features

- **Authentication & Authorization**
  - JWT-based authentication with access/refresh tokens
  - User registration with email verification
  - Password reset flow
  - Role-Based Access Control (RBAC)

- **Organization Management**
  - Multi-tenant organization structure
  - Hierarchical role management (Owner, Admin, Manager, Member, Guest)
  - Team invitations with email notifications

- **Workspace & Project Management**
  - Flexible workspace organization
  - Project methodology support (Scrum, Kanban, Waterfall)
  - Automatic workflow status creation
  - Team member management

- **File Storage**
  - Amazon S3 integration for file uploads
  - File validation (size, type)
  - Avatar and logo management

- **Email Delivery**
  - Amazon SES integration
  - Retry logic with exponential backoff
  - Welcome emails, password resets, invitations

- **Comprehensive Logging**
  - Audit logs for all major actions
  - Error tracking and alerting
  - System logs

---

## 📋 Prerequisites

- **Python 3.11+**
- **PostgreSQL 13+**
- **AWS Account** (for S3 and SES)
- **Git**

---

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/ficct-scrum-backend.git
cd ficct-scrum-backend
```

### 2. Create Virtual Environment

**Windows (Git Bash):**
```bash
python -m venv .venv
source .venv/Scripts/activate
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Required Environment Variables:**

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/ficct_scrum_db

# JWT
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440

# AWS S3
USE_S3=True
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_S3_BUCKET_NAME=your-s3-bucket-name
AWS_S3_REGION=us-east-1

# AWS SES
USE_SES=True
AWS_SES_REGION_NAME=us-east-1
DEFAULT_FROM_EMAIL=noreply@your-domain.com

# Frontend
FRONTEND_URL=http://localhost:4200
```

### 5. Database Setup

Create PostgreSQL database:

```bash
createdb ficct_scrum_db
```

Run migrations:

```bash
python manage.py migrate
```

**Seed default data (REQUIRED):**

```bash
python manage.py seed_issue_types
```

This creates default issue types (Epic, Story, Task, Bug, Improvement, Sub-task) for all projects. Without this step, issue creation will fail.

Create superuser:

```bash
python manage.py createsuperuser
```

### 6. AWS Configuration

#### S3 Bucket Setup:
1. Create an S3 bucket in AWS Console
2. Configure CORS for file uploads

#### SES Email Setup:
1. Verify sender email in AWS SES Console
2. Request production access
3. Configure SPF/DKIM for your domain

### 7. Verify AWS Services

**Test S3:**
```bash
python manage.py test_s3
```

**Test Email:**
```bash
python manage.py test_email --email=your-email@example.com
```

---

## 🏃 Running the Application

### Development Server

Activate virtual environment:
```bash
source .venv/Scripts/activate  # Windows
source .venv/bin/activate      # Linux/macOS
```

Run server:
```bash
python manage.py runserver
```

Access API at: `http://localhost:8000/api/`  
API Documentation: `http://localhost:8000/api/docs/`  
Admin Panel: `http://localhost:8000/admin/`

---

## 🧪 Running Tests

Execute full test suite with coverage:

```bash
source .venv/Scripts/activate
pytest --cov --cov-fail-under=70 -v
```

Run specific test module:

```bash
pytest apps/authentication/tests/test_api.py -v
```

---

## 📚 API Documentation

Interactive API documentation available at `/api/docs/`

### Authentication

All protected endpoints require JWT authentication:

```bash
# Register
POST /api/auth/register/

# Login
POST /api/auth/login/

# Use access token
Authorization: Bearer <access_token>
```

---

## 🔐 Security & Permissions

### Role Hierarchy

**Organization:** Owner > Admin > Manager > Member > Guest  
**Workspace:** Admin > Member  
**Project:** Lead > Admin > Developer > Viewer

### Permission Rules

1. Users must be organization members to join workspaces
2. Project creators automatically become project lead
3. Organization owners/admins have admin access to all workspaces

---

## 🗂️ Project Structure

```
ficct-scrum-backend/
├── apps/
│   ├── authentication/
│   ├── organizations/
│   ├── workspaces/
│   ├── projects/
│   └── logging/
├── base/
│   ├── services/
│   ├── storage/
│   ├── utils/
│   └── settings.py
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## 🚀 Production Deployment

### Pre-Deployment Checklist

```bash
python manage.py check --deploy
python manage.py migrate
pytest --cov --cov-fail-under=70
black --check apps/ base/
flake8 apps/ base/
```

---

## 🧹 Code Quality

Format code with Black:
```bash
black apps/ base/
```

Sort imports:
```bash
isort apps/ base/
```

Lint with Flake8:
```bash
flake8 apps/ base/
```

---

## 📊 Tech Stack

- Django 5.0.7
- Django REST Framework 3.15.2
- PostgreSQL
- Amazon S3 & SES
- pytest
- JWT Authentication

---

## 📝 License

MIT License

---

## 👥 Team

FICCT Development Team

---

**Virtual Environment:** Always activate with `source .venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Linux/macOS)
