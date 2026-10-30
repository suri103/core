// Mock API handlers for testing
import { http, HttpResponse } from 'msw';
import type { Patient, Appointment } from '@/types/api';

const API_BASE_URL = '/api/v1';

export const handlers = [
  // Auth endpoints
  http.post(`${API_BASE_URL}/auth/login`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string };
    
    if (body.email === 'demo@coredent.com' && body.password === 'demo123') {
      return HttpResponse.json({
        access_token: 'mock-access-token-123',
        refresh_token: 'mock-refresh-token-123',
        token_type: 'bearer',
        expires_in: 900,
        csrf_token: 'mock-csrf-token-123',
      });
    }
    
    return HttpResponse.json(
      { message: 'Invalid credentials' },
      { status: 401 }
    );
  }),

  http.get(`${API_BASE_URL}/auth/me`, () => {
    return HttpResponse.json({
      id: 'user-1',
      email: 'demo@coredent.com',
      firstName: 'Dr. Sarah',
      lastName: 'Johnson',
      role: 'dentist',
      practiceId: 'practice-1',
      practiceName: 'Bright Smile Dental',
    });
  }),
  http.post(`${API_BASE_URL}/auth/refresh`, async () => {
    return HttpResponse.json({
      access_token: 'mock-access-token-456',
      refresh_token: 'mock-refresh-token-456',
      token_type: 'bearer',
      expires_in: 900,
    });
  }),

  // Patient portal session cleanup is intentionally idempotent.
  http.post(`${API_BASE_URL}/portal/logout`, () => {
    return HttpResponse.json({ success: true });
  }),

  // Patients endpoints
  http.get(`${API_BASE_URL}/patients`, () => {
    return HttpResponse.json({
      data: [
        {
          id: 'patient-1',
          firstName: 'John',
          lastName: 'Doe',
          email: 'john.doe@example.com',
          phone: '555-0100',
          dateOfBirth: '1985-05-15',
          gender: 'male',
          address: {
            street: '123 Main St',
            city: 'Springfield',
            state: 'IL',
            zipCode: '62701',
          },
          emergencyContact: {
            name: 'Jane Doe',
            relationship: 'spouse',
            phone: '555-0101',
          },
          medicalAlerts: [],
          status: 'active',
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: '2024-01-01T00:00:00Z',
        } satisfies Patient,
      ],
      total: 1,
      page: 1,
      limit: 10,
      totalPages: 1,
    });
  }),

  http.get(`${API_BASE_URL}/patients/:id`, ({ params }) => {
    return HttpResponse.json({
      id: String(params.id),
      firstName: 'John',
      lastName: 'Doe',
      email: 'john.doe@example.com',
      phone: '555-0100',
      dateOfBirth: '1985-05-15',
      gender: 'male',
      address: {
        street: '123 Main St',
        city: 'Springfield',
        state: 'IL',
        zipCode: '62701',
      },
      emergencyContact: {
        name: 'Jane Doe',
        relationship: 'spouse',
        phone: '555-0101',
      },
      medicalAlerts: [],
      status: 'active',
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-01T00:00:00Z',
    } satisfies Patient);
  }),

  // Appointments endpoints
  http.get(`${API_BASE_URL}/appointments`, () => {
    return HttpResponse.json([
      {
        id: 'apt-1',
        patientId: 'patient-1',
        patientName: 'John Doe',
        providerId: 'provider-1',
        providerName: 'Dr. Smith',
        operatoryId: 'chair-1',
        operatoryName: 'Chair 1',
        type: 'cleaning',
        status: 'scheduled',
        startTime: new Date().toISOString(),
        endTime: new Date(Date.now() + 3600000).toISOString(),
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
      } satisfies Appointment,
    ]);
  }),

  // Clinic settings endpoints
  http.get(`${API_BASE_URL}/clinic/settings`, () => {
    return HttpResponse.json({
      id: 'clinic-1',
      name: 'Bright Smile Dental',
      email: 'info@brightsmile.com',
      phone: '555-0123',
      address: '123 Main Street',
      city: 'Springfield',
      state: 'IL',
      zipCode: '62701',
      country: 'USA',
      timezone: 'America/Chicago',
      currency: 'USD',
      logoUrl: null,
      workingHours: {
        monday: { enabled: true, start: '09:00', end: '17:00' },
        tuesday: { enabled: true, start: '09:00', end: '17:00' },
        wednesday: { enabled: true, start: '09:00', end: '17:00' },
        thursday: { enabled: true, start: '09:00', end: '17:00' },
        friday: { enabled: true, start: '09:00', end: '17:00' },
        saturday: { enabled: false, start: '09:00', end: '13:00' },
        sunday: { enabled: false, start: '09:00', end: '13:00' },
      },
      appointmentTypes: [
        {
          id: 'type-1',
          name: 'Cleaning',
          duration: 60,
          color: '#10b981',
          description: 'Regular dental cleaning',
          isActive: true,
        },
        {
          id: 'type-2',
          name: 'Exam',
          duration: 30,
          color: '#3b82f6',
          description: 'Dental examination',
          isActive: true,
        },
        {
          id: 'type-3',
          name: 'Filling',
          duration: 90,
          color: '#f59e0b',
          description: 'Dental filling procedure',
          isActive: true,
        },
      ],
      chairs: [
        {
          id: 'chair-1',
          name: 'Chair 1',
          isActive: true,
        },
        {
          id: 'chair-2',
          name: 'Chair 2',
          isActive: true,
        },
      ],
    });
  }),

  http.put(`${API_BASE_URL}/clinic/settings`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json(body);
  }),

  // Billing preferences endpoints
  http.get(`${API_BASE_URL}/settings/billing`, () => {
    return HttpResponse.json({
      taxRate: 0,
      currency: 'USD',
      invoicePrefix: 'INV',
      paymentTerms: 30,
      lateFeePercentage: 0,
      acceptedPaymentMethods: ['cash', 'card', 'check'],
      autoSendInvoices: false,
      autoSendReminders: true,
      reminderDaysBefore: 3,
    });
  }),

  http.put(`${API_BASE_URL}/settings/billing`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json(body);
  }),

  // Billing summary & invoices use the backend's raw snake_case wire contract.
  http.get(`${API_BASE_URL}/billing/summary`, () => {
    return HttpResponse.json({
      total_invoices: 120,
      total_revenue: 45000,
      total_tax: 0,
      total_payments: 100,
      total_collected: 40000,
      outstanding_balance: 5000,
      status_breakdown: [
        { status: 'paid', count: 100, amount: 40000 },
        { status: 'pending', count: 15, amount: 3800 },
        { status: 'overdue', count: 5, amount: 1200 },
      ],
    });
  }),

  http.get(`${API_BASE_URL}/billing/invoices/`, () => {
    return HttpResponse.json({
      invoices: [],
      count: 0,
      total: 0,
      limit: 50,
      offset: 0,
      next_offset: null,
    });
  }),

  http.get(`${API_BASE_URL}/invoices`, () => {
    return HttpResponse.json([]);
  }),

  // Reports dashboard
  http.get(`${API_BASE_URL}/reports/dashboard`, () => {
    return HttpResponse.json({
      appointments: {
        total: 60, completed: 45, cancelled: 10, noShow: 5,
        completionRate: 75, noShowRate: 8.3,
        byType: [{ type: 'checkup', count: 30 }],
        byDay: [{ day: '2026-06-01', count: 12 }],
      },
      revenue: {
        totalRevenue: 45000, totalCollected: 40000,
        totalOutstanding: 5000, averagePerVisit: 220,
        byMonth: [{ month: 'June', revenue: 45000, collected: 40000 }],
        byProcedure: [{ procedure: 'checkup', revenue: 15000 }],
      },
      treatmentAcceptance: {
        proposedPlans: 50, acceptedPlans: 40, completedPlans: 35,
        acceptanceRate: 80, completionRate: 87.5,
      },
      chairUtilization: {
        averageUtilization: 72, totalChairs: 4,
        peakHours: [{ hour: '10:00', utilization: 95 }],
        byChair: [{ chair: 'Chair 1', utilization: 80, appointments: 20 }],
        byDayOfWeek: [{ day: 'Monday', utilization: 85 }],
      },
    });
  }),

  // Communications endpoints
  http.get(`${API_BASE_URL}/communications/templates`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/communications/reminders`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/communications/conversations`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/communications/settings`, () => {
    return HttpResponse.json({
      unreadMessages: 0,
      messages: { totalSent: 0, deliveryRate: 0 },
      reminders: { pending: 0 },
    });
  }),

  // Insurance endpoints
  http.get(`${API_BASE_URL}/insurance/claims/`, () => {
    return HttpResponse.json({
      claims: [],
      count: 0,
      total: 0,
      limit: 50,
      offset: 0,
      next_offset: null,
    });
  }),

  http.get(`${API_BASE_URL}/insurance/carriers/`, () => {
    return HttpResponse.json({ carriers: [], count: 0 });
  }),

  http.get(`${API_BASE_URL}/insurance/pre-auth/`, () => {
    return HttpResponse.json({
      pre_authorizations: [],
      count: 0,
      total: 0,
      limit: 50,
      offset: 0,
      next_offset: null,
    });
  }),

  // Treatment plans
  http.get(`${API_BASE_URL}/treatment/plans/`, () => {
    return HttpResponse.json({ plans: [], count: 0, total: 0, next_offset: null });
  }),

  // Public booking
  http.get(`${API_BASE_URL}/booking/public/:slug`, ({ params }) => {
    return HttpResponse.json({
      page_slug: String(params.slug),
      page_title: 'Bright Smiles Booking',
      welcome_message: 'Welcome to our practice',
      logo_url: null,
      primary_color: '#2563EB',
      background_image_url: null,
      allow_new_patients: true,
      allow_existing_patients: true,
      require_phone_verification: true,
      require_email_verification: false,
      booking_window_days: 30,
      min_notice_hours: 24,
      practice_timezone: 'America/Chicago',
      business_hours: {},
      blocked_dates: [],
      allowed_appointment_types: ['11111111-1111-4111-8111-111111111111'],
      appointment_types: [{
        id: '11111111-1111-4111-8111-111111111111',
        name: 'Dental Checkup',
        duration_minutes: 30,
        description: 'Regular examination and cleaning',
        color: '#2563EB',
        icon: '🦷',
      }],
      providers: [{
        id: '22222222-2222-4222-8222-222222222222',
        name: 'Dr. Dana Dentist',
      }],
      intake_form_fields: [],
      require_insurance_info: false,
      require_medical_history: false,
      captcha_required: false,
    });
  }),

  http.post(`${API_BASE_URL}/booking/public/:slug/availability`, async ({ request }) => {
    const body = await request.json() as { start_date: string };
    return HttpResponse.json({
      days: [{
        date: body.start_date,
        day_of_week: 'Monday',
        is_available: true,
        slots: [{
          start_time: '09:00:00',
          end_time: '09:30:00',
          duration_minutes: 30,
          is_available: true,
          provider_id: '22222222-2222-4222-8222-222222222222',
          provider_name: 'Dr. Dana Dentist',
        }],
      }],
      total_slots: 1,
    });
  }),

  http.post(`${API_BASE_URL}/booking/public/:slug/book`, async ({ request }) => {
    const body = await request.json() as {
      first_name: string;
      last_name: string;
      requested_date: string;
      requested_time: string;
    };
    return HttpResponse.json({
      confirmation_code: 'ABC12345',
      status: 'pending',
      first_name: body.first_name,
      last_name: body.last_name,
      requested_date: body.requested_date,
      requested_time: body.requested_time,
      verification_session: 'mock-verification-session',
      require_email_verification: false,
      require_phone_verification: true,
      email_verified: true,
      phone_verified: false,
      message: 'Booking request submitted successfully',
    });
  }),

  http.post(`${API_BASE_URL}/booking/public/verify-email`, () => {
    return HttpResponse.json({
      verified: true,
      message: 'Email verified successfully',
      confirmation_code: 'ABC12345',
      email_verified: true,
      phone_verified: false,
      require_email_verification: true,
      require_phone_verification: true,
    });
  }),

  http.post(`${API_BASE_URL}/booking/public/verify-phone`, () => {
    return HttpResponse.json({
      verified: true,
      message: 'Phone verified successfully',
      confirmation_code: 'ABC12345',
      email_verified: true,
      phone_verified: true,
      require_email_verification: false,
      require_phone_verification: true,
    });
  }),
  // Subscriptions
  http.get(`${API_BASE_URL}/subscriptions/current`, () => {
    return HttpResponse.json(null);
  }),

  http.get(`${API_BASE_URL}/subscriptions/plans`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/subscriptions`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/subscriptions/stats`, () => {
    return HttpResponse.json(null);
  }),

  // Staff
  http.get(`${API_BASE_URL}/staff`, () => {
    return HttpResponse.json({ data: [], total: 0, page: 1, limit: 10, totalPages: 0 });
  }),

  http.get(`${API_BASE_URL}/staff/invitations`, () => {
    return HttpResponse.json([]);
  }),

  // Dental chart
  http.get(`${API_BASE_URL}/dental-chart/:patientId`, () => {
    return HttpResponse.json({ teeth: [], procedures: [] });
  }),

  // Imaging
  http.get(`${API_BASE_URL}/imaging/studies`, () => {
    return HttpResponse.json([]);
  }),

  // Automations
  http.get(`${API_BASE_URL}/automations`, () => {
    return HttpResponse.json([]);
  }),

  // Scheduling extras
  http.get(`${API_BASE_URL}/providers`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/chairs`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/appointment-types`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/referrals/`, () => {
    return HttpResponse.json({ referrals: [], count: 0 });
  }),

  // Referral sources (Referrals page)
  http.get(`${API_BASE_URL}/referrals/sources/`, () => {
    return HttpResponse.json({ sources: [], count: 0 });
  }),

  // Lab cases (Lab Management page)
  http.get(`${API_BASE_URL}/labs/cases/`, () => {
    return HttpResponse.json({ cases: [], count: 0 });
  }),

  // Lab vendors + lab invoices (Lab Management page)
  http.get(`${API_BASE_URL}/labs/vendors/`, () => {
    return HttpResponse.json({ labs: [], count: 0 });
  }),
  http.get(`${API_BASE_URL}/labs/invoices/`, () => {
    return HttpResponse.json({ invoices: [], count: 0 });
  }),
];


// Staff booking operations
const bookingFixture = {
  id: 'booking-1',
  booking_page_id: 'booking-page-1',
  practice_id: 'practice-1',
  patient_id: null,
  is_new_patient: false,
  first_name: 'Alex',
  last_name: 'Morgan',
  email: 'alex.morgan@example.com',
  phone: '555-0110',
  date_of_birth: '1990-04-12',
  appointment_type_id: 'appointment-type-1',
  provider_id: 'provider-1',
  requested_date: '2026-08-28',
  requested_time: '10:00',
  duration_minutes: 30,
  reason: 'Routine examination',
  chief_complaint: null,
  status: 'pending',
  confirmation_code: 'BOOK1234',
  email_verified: true,
  phone_verified: true,
  appointment_id: null,
  staff_notes: null,
  submitted_at: '2026-08-26T09:00:00Z',
  confirmed_at: null,
  declined_at: null,
  cancelled_at: null,
  cancellation_reason: null,
  created_at: '2026-08-26T09:00:00Z',
  updated_at: '2026-08-26T09:00:00Z',
};

const waitlistFixture = {
  id: 'waitlist-1',
  booking_page_id: 'booking-page-1',
  practice_id: 'practice-1',
  patient_id: 'patient-1',
  first_name: 'Jamie',
  last_name: 'Lee',
  email: 'jamie.lee@example.com',
  phone: '555-0111',
  preferred_dates: ['2026-08-29'],
  preferred_times: ['09:00'],
  appointment_type_id: 'appointment-type-1',
  reason: 'Earlier appointment requested',
  priority: 1,
  status: 'active',
  notified_count: 0,
  last_notified_at: null,
  expires_at: '2026-09-26T00:00:00Z',
  booking_id: null,
  created_at: '2026-08-26T09:05:00Z',
  updated_at: '2026-08-26T09:05:00Z',
};

handlers.push(
  http.get(`${API_BASE_URL}/booking/pages/`, () => HttpResponse.json({
    pages: [{
      id: 'booking-page-1',
      page_slug: 'bright-smile',
      page_title: 'Bright Smile Dental',
      status: 'active',
      total_bookings: 3,
      total_views: 40,
      conversion_rate: 7.5,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-08-26T00:00:00Z',
    }],
    count: 1,
    total: 1,
    limit: 20,
    offset: 0,
    next_offset: null,
  })),
  http.get(`${API_BASE_URL}/booking/bookings/`, () => HttpResponse.json({
    bookings: [bookingFixture],
    count: 1,
    total: 1,
    limit: 100,
    offset: 0,
    next_offset: null,
  })),
  http.put(`${API_BASE_URL}/booking/bookings/:bookingId`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...bookingFixture, ...body, id: String(params.bookingId) });
  }),
  http.post(`${API_BASE_URL}/booking/bookings/:bookingId/confirm`, ({ params }) => HttpResponse.json({
    booking_id: String(params.bookingId),
    appointment_id: 'appointment-1',
    confirmation_code: bookingFixture.confirmation_code,
    status: 'confirmed',
    message: 'Booking confirmed successfully',
  })),
  http.get(`${API_BASE_URL}/booking/waitlist/`, () => HttpResponse.json({
    entries: [waitlistFixture],
    count: 1,
    total: 1,
    limit: 100,
    offset: 0,
    next_offset: null,
  })),
  http.put(`${API_BASE_URL}/booking/waitlist/:entryId`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...waitlistFixture, ...body, id: String(params.entryId) });
  }),
  http.post(`${API_BASE_URL}/booking/waitlist/:entryId/notify`, () => HttpResponse.json({
    message: 'Notification accepted by the email provider',
    delivery_status: 'accepted',
    provider_accepted: true,
    provider_message_id: 'provider-message-1',
  })),
);

// Staff inventory operations
const inventoryFixtures = [
  {
    id: 'inventory-1',
    name: 'Nitrile gloves',
    description: 'Powder-free examination gloves',
    sku: 'GLOVE-M',
    barcode: null,
    category: 'disposable',
    unit: 'box',
    units_per_package: 100,
    current_quantity: 8,
    minimum_quantity: 10,
    reorder_quantity: 20,
    maximum_quantity: 40,
    unit_cost: '12.50',
    unit_price: null,
    storage_location: 'Supply room',
    track_expiration: false,
    expiration_warning_days: 30,
    supplier_name: 'Dental Supply Co.',
    supplier_item_code: null,
    is_active: true,
    is_trackable: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-08-26T00:00:00Z',
  },
  {
    id: 'inventory-2',
    name: 'Composite resin',
    description: 'Universal restorative composite',
    sku: 'RESIN-A2',
    barcode: null,
    category: 'restorative',
    unit: 'pack',
    units_per_package: 20,
    current_quantity: 24,
    minimum_quantity: 6,
    reorder_quantity: 12,
    maximum_quantity: 36,
    unit_cost: '48.00',
    unit_price: null,
    storage_location: 'Operatory cabinet',
    track_expiration: true,
    expiration_warning_days: 60,
    supplier_name: 'Dental Supply Co.',
    supplier_item_code: null,
    is_active: true,
    is_trackable: true,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-08-26T00:00:00Z',
  },
];

const inventoryAlertFixture = {
  id: 'alert-1',
  item_id: 'inventory-1',
  practice_id: 'practice-1',
  alert_type: 'low_stock',
  message: 'Nitrile gloves are at or below the minimum quantity',
  is_resolved: false,
  resolved_at: null,
  resolved_by: null,
  created_at: '2026-08-26T08:00:00Z',
};

handlers.push(
  http.get(`${API_BASE_URL}/inventory/items/`, ({ request }) => {
    const url = new URL(request.url);
    const search = (url.searchParams.get('search') || '').toLowerCase();
    const lowStock = url.searchParams.get('low_stock') === 'true';
    const items = inventoryFixtures.filter((item) => {
      const matchesSearch = !search || item.name.toLowerCase().includes(search) || item.sku.toLowerCase().includes(search);
      const matchesStock = !lowStock || item.current_quantity <= item.minimum_quantity;
      return matchesSearch && matchesStock;
    });
    return HttpResponse.json({ items, count: items.length, total: items.length, page: 1, limit: 100, pages: items.length ? 1 : 0 });
  }),
  http.post(`${API_BASE_URL}/inventory/items/`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...inventoryFixtures[0], ...body, id: 'inventory-created' }, { status: 201 });
  }),
  http.put(`${API_BASE_URL}/inventory/items/:itemId`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    const item = inventoryFixtures.find((candidate) => candidate.id === String(params.itemId)) || inventoryFixtures[0];
    return HttpResponse.json({ ...item, ...body, id: String(params.itemId) });
  }),
  http.delete(`${API_BASE_URL}/inventory/items/:itemId`, () => HttpResponse.json({ message: 'Inventory item deleted successfully' })),
  http.post(`${API_BASE_URL}/inventory/transactions/`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({
      id: 'transaction-1',
      item_id: body.item_id,
      practice_id: 'practice-1',
      user_id: 'user-1',
      transaction_type: body.transaction_type,
      quantity: body.quantity,
      previous_quantity: 8,
      new_quantity: 8,
      reference_type: null,
      reference_id: null,
      unit_cost: null,
      total_cost: null,
      notes: body.notes || null,
      created_at: '2026-08-26T10:00:00Z',
    });
  }),
  http.get(`${API_BASE_URL}/inventory/alerts/`, () => HttpResponse.json({
    alerts: [inventoryAlertFixture],
    count: 1,
    total: 1,
    page: 1,
    limit: 100,
    pages: 1,
  })),
  http.post(`${API_BASE_URL}/inventory/alerts/:alertId/resolve`, ({ params }) => HttpResponse.json({
    ...inventoryAlertFixture,
    id: String(params.alertId),
    is_resolved: true,
    resolved_at: '2026-08-26T10:00:00Z',
    resolved_by: 'user-1',
  })),
);

// Enterprise group operations
handlers.push(
  http.get(`${API_BASE_URL}/enterprise/group/analytics`, () => HttpResponse.json({
    group_id: 'group-1',
    period: { start: '2026-07-28T00:00:00Z', end: '2026-08-26T23:59:59Z' },
    consolidated: {
      production: 32500,
      collections: 28600,
      new_patients: 18,
      avg_utilization: 71.5,
    },
    by_location: [
      { practice_id: 'practice-1', practice_name: 'Bright Smile Dental', production: 18000, collections: 16000, new_patients: 11, utilization: 75 },
      { practice_id: 'practice-2', practice_name: 'Harbor Dental Care', production: 14500, collections: 12600, new_patients: 7, utilization: 68 },
    ],
  })),
  http.get(`${API_BASE_URL}/enterprise/group/practices`, () => HttpResponse.json([
    { id: 'practice-1', name: 'Bright Smile Dental', address_city: 'Springfield', address_state: 'IL' },
    { id: 'practice-2', name: 'Harbor Dental Care', address_city: 'Evanston', address_state: 'IL' },
  ])),

  // DSO Multi-Location Endpoints
  http.get(`${API_BASE_URL}/enterprise/dso/overview`, () => HttpResponse.json({
    group_id: 'group-1',
    total_clinics: 2,
    financials: {
      total_production: 32500,
      total_collections: 28600,
      total_outstanding_ar: 3900,
      collection_rate: 88.0,
    },
    ar_aging: {
      current_30: 2100,
      days_31_60: 1200,
      days_61_90: 450,
      over_90: 150,
    },
    locations: [
      {
        practice_id: 'practice-1',
        practice_name: 'Bright Smile Dental',
        city: 'Springfield',
        state: 'IL',
        chair_capacity: 4,
        active_providers: 3,
        active_patients: 120,
        production: 18000,
        collections: 16000,
        outstanding_ar: 2000,
      },
      {
        practice_id: 'practice-2',
        practice_name: 'Harbor Dental Care',
        city: 'Evanston',
        state: 'IL',
        chair_capacity: 3,
        active_providers: 2,
        active_patients: 95,
        production: 14500,
        collections: 12600,
        outstanding_ar: 1900,
      },
    ],
    provider_leaderboard: [
      {
        provider_id: 'prov-1',
        provider_name: 'Dr. Sarah Connor, DDS',
        role: 'DENTIST',
        clinic_name: 'Bright Smile Dental',
        completed_appointments: 48,
      },
      {
        provider_id: 'prov-2',
        provider_name: 'Dr. Edward Miller, DMD',
        role: 'DENTIST',
        clinic_name: 'Harbor Dental Care',
        completed_appointments: 36,
      },
    ],
  })),

  http.get(`${API_BASE_URL}/enterprise/dso/clinics`, () => HttpResponse.json([
    {
      id: 'practice-1',
      name: 'Bright Smile Dental',
      slug: 'bright-smile-dental',
      city: 'Springfield',
      state: 'IL',
      chair_capacity: 4,
      is_active: true,
    },
    {
      id: 'practice-2',
      name: 'Harbor Dental Care',
      slug: 'harbor-dental-care',
      city: 'Evanston',
      state: 'IL',
      chair_capacity: 3,
      is_active: true,
    },
  ])),

  http.post(`${API_BASE_URL}/enterprise/dso/switch-context`, async ({ request }) => {
    const body = (await request.json()) as any;
    const targetId = body?.target_practice_id || 'practice-1';
    return HttpResponse.json({
      success: true,
      access_token: 'dso-context-switched-token',
      active_practice_id: targetId,
      active_practice_name: targetId === 'practice-2' ? 'Harbor Dental Care' : 'Bright Smile Dental',
      message: 'Practice context switched successfully',
    });
  }),

  http.get(`${API_BASE_URL}/enterprise/dso/patients/search`, ({ request }) => {
    const url = new URL(request.url);
    const q = (url.searchParams.get('q') || '').toLowerCase();
    const all = [
      {
        id: 'patient-1',
        first_name: 'Alex',
        last_name: 'Morgan',
        date_of_birth: '1990-04-12',
        email: 'alex.morgan@example.com',
        phone: '555-0110',
        practice_id: 'practice-1',
        practice_name: 'Bright Smile Dental',
        practice_city: 'Springfield',
      },
      {
        id: 'patient-2',
        first_name: 'Jamie',
        last_name: 'Lee',
        date_of_birth: '1985-07-22',
        email: 'jamie.lee@example.com',
        phone: '555-0111',
        practice_id: 'practice-2',
        practice_name: 'Harbor Dental Care',
        practice_city: 'Evanston',
      },
    ];
    const filtered = all.filter(
      (p) =>
        p.first_name.toLowerCase().includes(q) ||
        p.last_name.toLowerCase().includes(q) ||
        p.email.toLowerCase().includes(q),
    );
    return HttpResponse.json(filtered);
  }),

  // Documents (L-5 fix: was previously a decorative page with hardcoded
  // mock data). MSW now serves the test fixtures so the page renders
  // and the L-5 wiring is exercised end-to-end.
  http.get(`${API_BASE_URL}/documents/templates`, () => HttpResponse.json([
    { id: '1', name: 'Patient Consent Form', type: 'Consent', lastUpdated: 'Jan 15, 2026', usage: 145 },
    { id: '2', name: 'HIPAA Privacy Notice', type: 'Legal', lastUpdated: 'Dec 1, 2025', usage: 89 },
    { id: '3', name: 'Treatment Plan Agreement', type: 'Financial', lastUpdated: 'Feb 5, 2026', usage: 67 },
    { id: '4', name: 'Financial Policy', type: 'Financial', lastUpdated: 'Jan 20, 2026', usage: 112 },
  ])),
  http.get(`${API_BASE_URL}/documents/`, () => HttpResponse.json([
    { id: '1', name: 'Consent Form - John Smith', patient: 'John Smith', type: 'Consent', status: 'Signed', date: 'Feb 10, 2026' },
    { id: '2', name: 'Treatment Plan - Jane Doe', patient: 'Jane Doe', type: 'Treatment', status: 'Pending Signature', date: 'Feb 12, 2026' },
    { id: '3', name: 'HIPAA - Bob Johnson', patient: 'Bob Johnson', type: 'Legal', status: 'Pending Signature', date: 'Feb 11, 2026' },
    { id: '4', name: 'Financial Policy - Mary Wilson', patient: 'Mary Wilson', type: 'Financial', status: 'Signed', date: 'Feb 8, 2026' },
  ])),
);
