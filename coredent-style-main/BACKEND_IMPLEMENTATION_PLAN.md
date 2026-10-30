# CoreDent Backend Implementation Plan

## Overview

The frontend is production-ready and needs a robust backend API. This document outlines the complete backend architecture and implementation plan.

---

## Technology Stack Recommendation

### Option 1: Node.js + Express (Recommended for Speed)
**Pros:**
- Same language as frontend (TypeScript)
- Fast development
- Large ecosystem
- Easy deployment

**Stack:**
- **Runtime:** Node.js 20+
- **Framework:** Express.js or Fastify
- **Database:** PostgreSQL 15+
- **ORM:** Prisma or TypeORM
- **Authentication:** JWT + Passport.js
- **Validation:** Zod (matches frontend)
- **File Storage:** AWS S3 or MinIO
- **Cache:** Redis
- **Queue:** Bull (Redis-based)

### Option 2: Python + FastAPI (Recommended for Healthcare)
**Pros:**
- Excellent for healthcare/ML features
- Strong typing with Pydantic
- Auto-generated API docs
- HIPAA compliance libraries

**Stack:**
- **Framework:** FastAPI
- **Database:** PostgreSQL 15+
- **ORM:** SQLAlchemy 2.0
- **Authentication:** JWT + OAuth2
- **Validation:** Pydantic
- **File Storage:** AWS S3
- **Cache:** Redis
- **Queue:** Celery

### Option 3: Go + Fiber (Recommended for Performance)
**Pros:**
- Extremely fast
- Low resource usage
- Built-in concurrency
- Strong typing

**Stack:**
- **Framework:** Fiber or Gin
- **Database:** PostgreSQL 15+
- **ORM:** GORM
- **Authentication:** JWT
- **Cache:** Redis
- **Queue:** Asynq

---

## Database Schema

### Core Tables

```sql
-- Users & Authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('owner', 'admin', 'dentist', 'hygienist', 'front_desk')),
    practice_id UUID REFERENCES practices(id),
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Practices/Clinics
CREATE TABLE practices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    address_street VARCHAR(255),
    address_city VARCHAR(100),
    address_state VARCHAR(2),
    address_zip VARCHAR(10),
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    currency VARCHAR(3) DEFAULT 'USD',
    logo_url TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Patients
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practice_id UUID REFERENCES practices(id) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20),
    email VARCHAR(255),
    phone VARCHAR(20),
    address_street VARCHAR(255),
    address_city VARCHAR(100),
    address_state VARCHAR(2),
    address_zip VARCHAR(10),
    emergency_contact JSONB,
    medical_alerts TEXT[],
    medical_history JSONB DEFAULT '{}',
    dental_history JSONB DEFAULT '{}',
    insurance_info JSONB,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Appointments
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practice_id UUID REFERENCES practices(id) NOT NULL,
    patient_id UUID REFERENCES patients(id) NOT NULL,
    provider_id UUID REFERENCES users(id),
    chair_id UUID REFERENCES chairs(id),
    appointment_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    duration INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Chairs/Operatories
CREATE TABLE chairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practice_id UUID REFERENCES practices(id) NOT NULL,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7) DEFAULT '#6B7280',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Appointment Types
CREATE TABLE appointment_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practice_id UUID REFERENCES practices(id) NOT NULL,
    name VARCHAR(100) NOT NULL,
    duration INTEGER NOT NULL,
    color VARCHAR(7) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Clinical Notes
CREATE TABLE clinical_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    provider_id UUID REFERENCES users(id) NOT NULL,
    appointment_id UUID REFERENCES appointments(id),
    note_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    attachments JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Dental Chart
CREATE TABLE dental_charts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) UNIQUE NOT NULL,
    chart_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Treatment Plans
CREATE TABLE treatment_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    provider_id UUID REFERENCES users(id) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    total_cost DECIMAL(10, 2),
    procedures JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Invoices
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practice_id UUID REFERENCES practices(id) NOT NULL,
    patient_id UUID REFERENCES patients(id) NOT NULL,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    subtotal DECIMAL(10, 2) NOT NULL,
    tax DECIMAL(10, 2) DEFAULT 0,
    total DECIMAL(10, 2) NOT NULL,
    line_items JSONB NOT NULL,
    due_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Payments
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id) NOT NULL,
    patient_id UUID REFERENCES patients(id) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'completed',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit Log
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sessions (for JWT refresh tokens)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    refresh_token VARCHAR(500) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_provider ON appointments(provider_id);
CREATE INDEX idx_appointments_start_time ON appointments(start_time);
CREATE INDEX idx_patients_practice ON patients(practice_id);
CREATE INDEX idx_patients_email ON patients(email);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_invoices_patient ON invoices(patient_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
```

---

## API Endpoints

### Authentication
```
POST   /api/auth/login              - Login with email/password
POST   /api/auth/logout             - Logout and invalidate token
POST   /api/auth/refresh            - Refresh access token
GET    /api/auth/me                 - Get current user
POST   /api/auth/forgot-password    - Request password reset
POST   /api/auth/reset-password     - Reset password with token
POST   /api/auth/invitations/accept - Accept staff invitation
GET    /api/auth/invitations/validate - Validate invitation token
```

### Patients
```
GET    /api/patients                - List patients (with pagination, search, filters)
GET    /api/patients/:id            - Get patient details
POST   /api/patients                - Create patient
PUT    /api/patients/:id            - Update patient
DELETE /api/patients/:id            - Delete patient (soft delete)
GET    /api/patients/:id/chart      - Get dental chart
PUT    /api/patients/:id/chart      - Update dental chart
GET    /api/patients/:id/notes      - Get clinical notes
GET    /api/patients/:id/treatment-plans - Get treatment plans
GET    /api/patients/:id/ledger     - Get financial ledger
```

### Appointments
```
GET    /api/appointments            - List appointments (by date range)
GET    /api/appointments/:id        - Get appointment details
POST   /api/appointments            - Create appointment
PUT    /api/appointments/:id        - Update appointment
DELETE /api/appointments/:id        - Cancel appointment
PATCH  /api/appointments/:id/status - Update appointment status
POST   /api/appointments/:id/reschedule - Reschedule appointment
```

### Clinical Notes
```
GET    /api/notes                   - List notes (by patient)
GET    /api/notes/:id               - Get note details
POST   /api/notes                   - Create note
PUT    /api/notes/:id               - Update note
DELETE /api/notes/:id               - Delete note
```

### Treatment Plans
```
GET    /api/treatment-plans         - List treatment plans
GET    /api/treatment-plans/:id     - Get treatment plan
POST   /api/treatment-plans         - Create treatment plan
PUT    /api/treatment-plans/:id     - Update treatment plan
DELETE /api/treatment-plans/:id     - Delete treatment plan
```

### Billing
```
GET    /api/invoices                - List invoices
GET    /api/invoices/:id            - Get invoice details
POST   /api/invoices                - Create invoice
PUT    /api/invoices/:id            - Update invoice
POST   /api/payments                - Record payment
GET    /api/billing/summary         - Get billing summary
```

### Reports
```
GET    /api/reports/production      - Production report
GET    /api/reports/appointments    - Appointment report
GET    /api/reports/dashboard       - Dashboard metrics
```

### Settings
```
GET    /api/clinic/settings         - Get clinic settings
PUT    /api/clinic/settings         - Update clinic settings
POST   /api/clinic/logo             - Upload clinic logo
GET    /api/clinic/chairs           - List chairs
POST   /api/clinic/chairs           - Create chair
PUT    /api/clinic/chairs/:id       - Update chair
DELETE /api/clinic/chairs/:id       - Delete chair
GET    /api/clinic/appointment-types - List appointment types
POST   /api/clinic/appointment-types - Create appointment type
PUT    /api/clinic/appointment-types/:id - Update appointment type
DELETE /api/clinic/appointment-types/:id - Delete appointment type
GET    /api/settings/billing        - Get billing preferences
PUT    /api/settings/billing        - Update billing preferences
```

### Staff Management
```
GET    /api/staff                   - List staff members
POST   /api/staff/invite            - Invite staff member
PUT    /api/staff/:id               - Update staff member
DELETE /api/staff/:id               - Remove staff member
```

---

## Security Requirements

### Authentication
- JWT tokens with 15-minute expiration
- Refresh tokens with 7-day expiration
- CSRF token validation on all state-changing requests
- Rate limiting: 100 requests/15 minutes per IP
- Password requirements: 8+ chars, uppercase, lowercase, number

### Authorization
- Role-based access control (RBAC)
- Resource-level permissions
- Audit logging for all sensitive operations

### Data Protection
- Encryption at rest (database encryption)
- Encryption in transit (TLS 1.3)
- HIPAA compliance measures
- PHI data handling protocols
- Secure file storage with signed URLs

### API Security
- Input validation on all endpoints
- SQL injection prevention (parameterized queries)
- XSS prevention (output encoding)
- CORS configuration
- Request size limits
- File upload validation

---

## Implementation Timeline

### Phase 1: Core Backend (2-3 weeks)
- [ ] Set up project structure
- [ ] Database schema and migrations
- [ ] Authentication system
- [ ] User management
- [ ] Basic CRUD for patients
- [ ] Basic CRUD for appointments

### Phase 2: Clinical Features (2-3 weeks)
- [ ] Dental chart API
- [ ] Clinical notes
- [ ] Treatment plans
- [ ] File upload/storage
- [ ] Search functionality

### Phase 3: Billing & Reports (2 weeks)
- [ ] Invoice management
- [ ] Payment processing
- [ ] Financial reports
- [ ] Dashboard metrics
- [ ] Export functionality

### Phase 4: Advanced Features (2 weeks)
- [ ] Email notifications
- [ ] SMS reminders
- [ ] Automated workflows
- [ ] Backup system
- [ ] Performance optimization

### Phase 5: Testing & Deployment (1-2 weeks)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Load testing
- [ ] Security audit
- [ ] Production deployment

**Total Estimated Time: 9-12 weeks**

---

## Deployment Architecture

```
┌─────────────────┐
│   Load Balancer │
│    (nginx)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│ API 1 │ │ API 2 │  (Node.js/Python/Go)
└───┬───┘ └──┬────┘
    │        │
    └────┬───┘
         │
    ┌────▼────────┐
    │ PostgreSQL  │
    │  (Primary)  │
    └─────────────┘
         │
    ┌────▼────────┐
    │ PostgreSQL  │
    │  (Replica)  │
    └─────────────┘
         
    ┌─────────────┐
    │    Redis    │
    │ (Cache/Queue)│
    └─────────────┘
    
    ┌─────────────┐
    │   AWS S3    │
    │ (File Store)│
    └─────────────┘
```

---

## Cost Estimate

### Development
- Backend Developer: $80-150/hour × 400 hours = $32,000-60,000
- DevOps Setup: $5,000-10,000
- Testing & QA: $5,000-10,000
**Total Development: $42,000-80,000**

### Monthly Operating Costs
- Server (2× API instances): $100-200/month
- Database (PostgreSQL): $50-150/month
- Redis: $20-50/month
- S3 Storage: $10-50/month
- Monitoring (Sentry, etc.): $50-100/month
- Email Service: $20-50/month
- SMS Service: $50-200/month
**Total Monthly: $300-800/month**

---

## Next Steps

1. **Choose Technology Stack** - Recommend Node.js + Express for fastest development
2. **Set Up Development Environment** - Docker, PostgreSQL, Redis
3. **Create Backend Repository** - Initialize project structure
4. **Implement Phase 1** - Core authentication and basic CRUD
5. **Connect Frontend** - Update API_BASE_URL and test integration

Would you like me to:
1. Generate the complete backend code for Node.js + Express?
2. Create a Python FastAPI implementation?
3. Build a Go backend?
4. Start with just the authentication and user management module?
