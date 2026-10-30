# API Documentation

## Base URL

```
Development: http://localhost:3000/api
Production: https://api.coredent.com
```

## Authentication

All authenticated endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <token>
```

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (audited snake_case auth contract):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 900,
  "csrf_token": "..."
}
```

### Logout

```http
POST /auth/logout
Authorization: Bearer <token>
```

### Get Current User

```http
GET /auth/me
Authorization: Bearer <token>
```

## Patients

### List Patients

```http
GET /patients?search=john&status=active&page=1&pageSize=20
Authorization: Bearer <token>
```

**Query Parameters:**
- `search` (optional): Search by name, email, or phone
- `status` (optional): `active` | `inactive`
- `page` (optional): Page number (default: 1)
- `pageSize` (optional): Items per page (default: 20)

**Response:**
```json
{
  "data": [
    {
      "id": "patient-123",
      "firstName": "John",
      "lastName": "Doe",
      "email": "john.doe@example.com",
      "phone": "555-0100",
      "dateOfBirth": "1985-05-15",
      "status": "active",
      "address": {
        "street": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "zipCode": "12345"
      },
      "createdAt": "2024-01-15T10:00:00Z",
      "updatedAt": "2024-02-01T14:30:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "pageSize": 20
}
```

### Get Patient

```http
GET /patients/:id
Authorization: Bearer <token>
```

### Create Patient

```http
POST /patients
Authorization: Bearer <token>
Content-Type: application/json

{
  "firstName": "Jane",
  "lastName": "Smith",
  "email": "jane.smith@example.com",
  "phone": "555-0200",
  "dateOfBirth": "1990-08-20",
  "address": {
    "street": "456 Oak Ave",
    "city": "Springfield",
    "state": "IL",
    "zipCode": "62701"
  },
  "emergencyContact": {
    "name": "John Smith",
    "relationship": "Spouse",
    "phone": "555-0201"
  },
  "insurance": {
    "provider": "Blue Cross",
    "policyNumber": "BC123456",
    "groupNumber": "GRP789"
  }
}
```

### Update Patient

```http
PUT /patients/:id
Authorization: Bearer <token>
Content-Type: application/json

{
  "phone": "555-0300",
  "email": "newemail@example.com"
}
```

### Delete Patient

```http
DELETE /patients/:id
Authorization: Bearer <token>
```

## Appointments

### List Appointments

```http
GET /appointments?startDate=2024-02-01&endDate=2024-02-29&providerId=provider-123
Authorization: Bearer <token>
```

**Query Parameters:**
- `startDate` (required): ISO 8601 date
- `endDate` (required): ISO 8601 date
- `providerId` (optional): Filter by provider
- `status` (optional): Filter by status

**Response:**
```json
[
  {
    "id": "apt-123",
    "patientId": "patient-123",
    "patientName": "John Doe",
    "providerId": "provider-456",
    "providerName": "Dr. Smith",
    "type": "cleaning",
    "status": "scheduled",
    "startTime": "2024-02-15T10:00:00Z",
    "endTime": "2024-02-15T11:00:00Z",
    "duration": 60,
    "notes": "Regular cleaning",
    "createdAt": "2024-02-01T09:00:00Z",
    "updatedAt": "2024-02-01T09:00:00Z"
  }
]
```

### Create Appointment

```http
POST /appointments
Authorization: Bearer <token>
Content-Type: application/json

{
  "patientId": "patient-123",
  "providerId": "provider-456",
  "type": "cleaning",
  "startTime": "2024-02-15T10:00:00Z",
  "duration": 60,
  "notes": "Regular cleaning"
}
```

### Update Appointment

```http
PUT /appointments/:id
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "confirmed",
  "notes": "Patient confirmed via phone"
}
```

### Delete Appointment

```http
DELETE /appointments/:id
Authorization: Bearer <token>
```

## Dental Chart

### Get Patient Chart

```http
GET /patients/:patientId/chart
Authorization: Bearer <token>
```

**Response:**
```json
{
  "patientId": "patient-123",
  "patientName": "John Doe",
  "teeth": [
    {
      "number": 1,
      "name": "Upper Right Third Molar",
      "condition": "healthy",
      "procedures": [
        {
          "id": "proc-123",
          "procedureCode": "D1110",
          "procedureName": "Prophylaxis - Adult",
          "surfaces": ["O", "B"],
          "status": "completed",
          "date": "2024-01-15",
          "dentistId": "dentist-456",
          "dentistName": "Dr. Smith",
          "notes": "Routine cleaning",
          "color": "#3b82f6"
        }
      ]
    }
  ],
  "lastUpdated": "2024-02-01T10:00:00Z"
}
```

### Update Tooth Condition

```http
PUT /patients/:patientId/chart/teeth/:toothNumber
Authorization: Bearer <token>
Content-Type: application/json

{
  "condition": "watch"
}
```

### Add Procedure

```http
POST /patients/:patientId/chart/procedures
Authorization: Bearer <token>
Content-Type: application/json

{
  "toothNumber": 14,
  "procedureCode": "D2391",
  "procedureName": "Resin-based composite - one surface",
  "surfaces": ["O"],
  "status": "planned",
  "notes": "Small cavity on occlusal surface"
}
```

## Invoices

### List Invoices

```http
GET /invoices?patientId=patient-123&status=pending
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "id": "inv-123",
    "invoiceNumber": "INV-2024-001",
    "patientId": "patient-123",
    "patientName": "John Doe",
    "patientEmail": "john.doe@example.com",
    "issueDate": "2024-02-01",
    "dueDate": "2024-02-15",
    "status": "sent",
    "lineItems": [
      {
        "id": "item-1",
        "procedureCode": "D1110",
        "description": "Prophylaxis - Adult",
        "quantity": 1,
        "unitPrice": 120.00,
        "discount": 0,
        "total": 120.00
      }
    ],
    "subtotal": 120.00,
    "tax": 0,
    "total": 120.00,
    "amountPaid": 0,
    "balance": 120.00,
    "payments": [],
    "notes": "",
    "createdAt": "2024-02-01T10:00:00Z",
    "updatedAt": "2024-02-01T10:00:00Z"
  }
]
```

### Create Invoice

```http
POST /invoices
Authorization: Bearer <token>
Content-Type: application/json

{
  "patientId": "patient-123",
  "dueDate": "2024-02-15",
  "lineItems": [
    {
      "procedureCode": "D1110",
      "description": "Prophylaxis - Adult",
      "quantity": 1,
      "unitPrice": 120.00,
      "discount": 0
    }
  ],
  "notes": "Thank you for your business"
}
```

### Record Payment

```http
POST /payments
Authorization: Bearer <token>
Content-Type: application/json

{
  "invoiceId": "inv-123",
  "amount": 120.00,
  "method": "credit_card",
  "reference": "CH_1234567890",
  "notes": "Paid in full"
}
```

## Reports

### Production Report

```http
GET /reports/production?from=2024-02-01&to=2024-02-29&providerId=provider-123
Authorization: Bearer <token>
```

**Response:**
```json
{
  "period": {
    "from": "2024-02-01",
    "to": "2024-02-29"
  },
  "totalProduction": 15000.00,
  "totalCollections": 12000.00,
  "outstandingBalance": 3000.00,
  "byProvider": [
    {
      "providerId": "provider-123",
      "providerName": "Dr. Smith",
      "production": 10000.00,
      "collections": 8000.00
    }
  ],
  "byProcedure": [
    {
      "procedureCode": "D1110",
      "procedureName": "Prophylaxis - Adult",
      "count": 50,
      "revenue": 6000.00
    }
  ]
}
```

### Appointment Report

```http
GET /reports/appointments?from=2024-02-01&to=2024-02-29
Authorization: Bearer <token>
```

## Error Responses

All errors follow this format:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common Error Codes

- `VALIDATION_ERROR` (400): Invalid request data
- `UNAUTHORIZED` (401): Missing or invalid token
- `FORBIDDEN` (403): Insufficient permissions
- `NOT_FOUND` (404): Resource not found
- `CONFLICT` (409): Resource conflict
- `INTERNAL_ERROR` (500): Server error

## Rate Limiting

- 100 requests per minute per user
- 429 status code when exceeded
- `Retry-After` header indicates wait time

## Pagination

List endpoints support pagination:

```
?page=1&pageSize=20
```

Response includes:
```json
{
  "data": [...],
  "total": 150,
  "page": 1,
  "pageSize": 20
}
```

## Filtering & Sorting

Most list endpoints support:

**Filtering:**
```
?status=active&role=dentist
```

**Sorting:**
```
?sortBy=createdAt&sortOrder=desc
```

## Webhooks (Coming Soon)

Subscribe to events:
- `appointment.created`
- `appointment.updated`
- `appointment.cancelled`
- `payment.received`
- `invoice.created`

---

## Current endpoint contract notes (audited 2026-08-09)

The frontend mount point is `/api/v1`. Request bodies and query params are
sent camelCase and normalised to snake_case at the api boundary for the
normalised domains; responses are normalised back to camelCase. See
`docs/PAYLOAD_CONTRACT_AUDIT.md` for the full per-domain matrix.

### Appointments

- `GET /appointments?start_date&end_date&status&provider_id&patient_id` →
  `{ "appointments": [...], "count": N }`.
- Each appointment now also carries read-model aliases after case
  normalisation: `type` (= `appointment_type`), `patientName`,
  `providerName`, `operatoryId`/`operatoryName` (from the chair).
- `PUT /appointments/{id}/status` — body `{ "status": "<status>" }`.
- `POST /appointments/{id}/cancel` — body `{ "reason": "<optional>" }`.
- `PUT /appointments/{id}/reschedule` — body `{ "chair_id?", "start_time?" }`.
- Statuses: `scheduled | confirmed | checked_in | in_progress | completed |
  cancelled | no_show`.
- Create/update accept human-readable type names (`"Checkup"`, `"Root Canal"`,
  `"Follow-up"`) alongside the enum values.

### Clinical notes

- `GET|POST /notes`, `GET|PUT|DELETE /notes/{id}`, `GET /patients/{id}/notes`.
- Create body: `{ patient_id, type, provider_id?, appointment_id?, content?,
  subjective?, objective?, assessment?, plan?, attachments? }`.
- `type` ∈ `soap | procedure | treatment | consultation | progress |
  follow_up | general`.

### Reference / scheduling lookups

- `GET /providers` → `[{ id, name, role }]`
- `GET /chairs` → `[{ id, name, color, description, is_active }]`
- `GET /appointment-types` → configured types, falling back to the standard
  dental set `[{ id, name, code, duration, color, is_active,
  allow_online_booking, description }]`
- `GET /patients/search?query=` → `[{ id, name, phone, email? }]`

### Patient export (GDPR/HIPAA portability)

- `GET /patients/{id}/export` (OWNER/ADMIN only) → `PatientExportResponse`
  envelope: `exported_at`, `exported_by { id, name, role }`, plus portable
  per-section rows for `patient_demographics`, `appointments`, `clinical_notes`,
  `treatment_plans`, `invoices`, `payments`, `insurances`, `insurance_claims`,
  `patient_images`, `documents`.

---

Last updated: August 2026
