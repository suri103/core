# CoreDent API - FastAPI Backend

Production-ready FastAPI backend for CoreDent Dental Practice Management System.

## Features

- ✅ FastAPI with async/await
- ✅ PostgreSQL with SQLAlchemy 2.0
- ✅ JWT Authentication with refresh tokens
- ✅ CSRF Protection
- ✅ Role-based access control (RBAC)
- ✅ Pydantic validation
- ✅ HIPAA compliance ready
- ✅ Comprehensive error handling
- ✅ API documentation (Swagger/ReDoc)
- ✅ Database migrations (Alembic)
- ✅ Docker support
- ✅ Rate limiting
- ✅ Audit logging

## Tech Stack

- **Framework:** FastAPI 0.109+
- **Database:** PostgreSQL 15+
- **ORM:** SQLAlchemy 2.0
- **Validation:** Pydantic v2
- **Authentication:** JWT (python-jose)
- **Password Hashing:** bcrypt
- **Migrations:** Alembic
- **Testing:** pytest
- **ASGI Server:** uvicorn

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis (optional, for caching)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 3000
```

### Docker Setup

```bash
# Build and run with Docker Compose
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Create initial admin user
docker-compose exec api python scripts/create_admin.py
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:3000/docs
- ReDoc: http://localhost:3000/redoc
- OpenAPI JSON: http://localhost:3000/openapi.json

## Project Structure

```
coredent-api/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py
│   │   │   │   ├── patients.py
│   │   │   │   ├── appointments.py
│   │   │   │   ├── billing.py
│   │   │   │   └── ...
│   │   │   └── api.py
│   │   └── deps.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── database.py
│   ├── models/
│   │   ├── user.py
│   │   ├── patient.py
│   │   └── ...
│   ├── schemas/
│   │   ├── user.py
│   │   ├── patient.py
│   │   └── ...
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── patient_service.py
│   │   └── ...
│   └── main.py
├── alembic/
│   └── versions/
├── tests/
├── scripts/
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/coredent

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:8080,http://localhost:5173

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-password

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_BUCKET=coredent-files
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current version
alembic current
```

## Deployment

### Production Checklist

- [ ] Set strong SECRET_KEY
- [ ] Configure production database
- [ ] Set up SSL/TLS
- [ ] Configure CORS properly
- [ ] Enable rate limiting
- [ ] Set up monitoring (Sentry)
- [ ] Configure backup strategy
- [ ] Set up log aggregation
- [ ] Enable HTTPS only
- [ ] Configure firewall rules

### Deploy with Docker

```bash
# Build production image
docker build -t coredent-api:latest .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/logout` - Logout
- `POST /api/v1/auth/refresh` - Refresh token
- `GET /api/v1/auth/me` - Current user
- `POST /api/v1/auth/forgot-password` - Request reset
- `POST /api/v1/auth/reset-password` - Reset password

### Patients
- `GET /api/v1/patients` - List patients
- `POST /api/v1/patients` - Create patient
- `GET /api/v1/patients/{id}` - Get patient
- `PUT /api/v1/patients/{id}` - Update patient
- `DELETE /api/v1/patients/{id}` - Delete patient

### Appointments
- `GET /api/v1/appointments` - List appointments
- `POST /api/v1/appointments` - Create appointment
- `GET /api/v1/appointments/{id}` - Get appointment
- `PUT /api/v1/appointments/{id}` - Update appointment
- `DELETE /api/v1/appointments/{id}` - Cancel appointment

[See full API documentation at /docs]

## Security

### HIPAA Compliance

This backend implements several HIPAA-required features:
- Audit logging of all PHI access
- Encryption at rest and in transit
- Access controls and authentication
- Automatic session timeout
- Password complexity requirements

### Security Features

- JWT with short expiration (15 min)
- Refresh token rotation
- CSRF protection
- Rate limiting
- SQL injection prevention
- XSS prevention
- Input validation
- Secure password hashing (bcrypt)

## Performance

- Async/await for non-blocking I/O
- Database connection pooling
- Query optimization with indexes
- Redis caching (optional)
- Response compression

## Monitoring

- Health check endpoint: `/health`
- Metrics endpoint: `/metrics`
- Structured logging
- Error tracking (Sentry integration)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md)

## License

Proprietary - CoreDent PMS

## Support

- Email: support@coredent.com
- Documentation: https://docs.coredent.com
- Issues: https://github.com/coredent/api/issues
