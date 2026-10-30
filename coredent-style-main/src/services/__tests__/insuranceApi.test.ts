import { beforeEach, describe, expect, it } from 'vitest';
import { HttpResponse, http } from 'msw';
import { insuranceApi } from '../insuranceApi';
import { server } from '@/test/mocks/server';

const carrierWire = {
  id: 'car-1',
  name: 'Delta Dental',
  phone: '800-555-0000',
  fax: null,
  email: 'claims@delta.example',
  website: null,
  address_line1: 'PO Box 1',
  address_line2: null,
  city: 'Sacramento',
  state: 'CA',
  zip_code: '95814',
  payer_id: 'DEL-001',
  edi_enabled: true,
  notes: null,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const policyWire = {
  id: 'pol-1',
  patient_id: 'p-1',
  carrier_id: 'car-1',
  subscriber_id: 'SUB-001',
  group_number: 'GRP-1',
  relationship_to_subscriber: 'self',
  is_primary: true,
  is_active: true,
  coverage_type: 'PPO',
  annual_maximum: '1500.00',
  annual_deductible: '50.00',
  deductible_met: '20.00',
  benefits_used: '125.50',
  preventive_coverage: 100,
  basic_coverage: 80,
  major_coverage: 50,
  ortho_coverage: 0,
  effective_date: '2026-01-01',
  expiration_date: null,
  verified: false,
  verified_at: null,
  verified_by: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const claimWire = {
  id: 'cl-1',
  practice_id: 'practice-1',
  patient_id: 'p-1',
  patient_insurance_id: 'pol-1',
  carrier_id: 'car-1',
  claim_number: 'CLM-001',
  status: 'draft',
  service_date: '2026-06-01',
  submission_date: null,
  received_date: null,
  paid_date: null,
  billed_amount: '120.00',
  allowed_amount: null,
  deductible_amount: '0.00',
  copay_amount: '0.00',
  paid_amount: '0.00',
  patient_responsibility: '0.00',
  procedure_codes: [{ code: 'D1110', description: 'Cleaning', fee: '120.00' }],
  diagnosis_codes: [],
  notes: null,
  denial_reason: null,
  edi_transaction_id: null,
  edi_batch_id: null,
  confirmation_number: null,
  outstanding_balance: 120,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const preAuthWire = {
  id: 'pa-1',
  patient_id: 'p-1',
  patient_insurance_id: 'pol-1',
  authorization_number: 'PA-20260601-ABC12345',
  status: 'pending',
  request_date: '2026-06-01',
  procedure_codes: [{ code: 'D1110', description: 'Cleaning', fee: '120.00' }],
  estimated_cost: '120.00',
  approval_date: null,
  expiration_date: null,
  approved_amount: null,
  notes: null,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

describe('insuranceApi', () => {
  beforeEach(() => server.resetHandlers());

  describe('carriers', () => {
    it('maps the backend list envelope and snake_case fields', async () => {
      server.use(http.get('/api/v1/insurance/carriers/', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('is_active')).toBe('true');
        expect(url.searchParams.get('search')).toBe('delta');
        return HttpResponse.json({ carriers: [carrierWire], count: 1 });
      }));

      const result = await insuranceApi.getCarriers({ search: 'delta', isActive: true });

      expect(result).toEqual([expect.objectContaining({
        id: 'car-1',
        payerId: 'DEL-001',
        ediEnabled: true,
        addressLine1: 'PO Box 1',
        isActive: true,
      })]);
    });

    it('posts an explicit snake_case carrier payload and maps the response', async () => {
      server.use(http.post('/api/v1/insurance/carriers/', async ({ request }) => {
        expect(await request.json()).toEqual({
          name: 'Aetna',
          address_line1: 'Claims Office',
          payer_id: 'AETNA-1',
          edi_enabled: true,
          is_active: true,
        });
        return HttpResponse.json({
          ...carrierWire,
          id: 'car-2',
          name: 'Aetna',
          address_line1: 'Claims Office',
          payer_id: 'AETNA-1',
        });
      }));

      const result = await insuranceApi.createCarrier({
        name: 'Aetna',
        addressLine1: 'Claims Office',
        payerId: 'AETNA-1',
        ediEnabled: true,
        isActive: true,
      });

      expect(result).toEqual(expect.objectContaining({ id: 'car-2', payerId: 'AETNA-1' }));
    });

    it('surfaces backend carrier errors', async () => {
      server.use(http.post('/api/v1/insurance/carriers/', () =>
        HttpResponse.json({ detail: 'Carrier already exists' }, { status: 409 }),
      ));

      await expect(insuranceApi.createCarrier({ name: 'Aetna' })).rejects.toThrow('Carrier already exists');
    });
  });

  describe('patient policies', () => {
    it('maps real policy attributes and Decimal values', async () => {
      server.use(http.get('/api/v1/insurance/patients/p-1/policies', () =>
        HttpResponse.json({ insurances: [policyWire], count: 1 }),
      ));

      const result = await insuranceApi.getPatientInsurance('p-1');

      expect(result).toEqual([expect.objectContaining({
        patientId: 'p-1',
        carrierId: 'car-1',
        subscriberId: 'SUB-001',
        isPrimary: true,
        annualMaximum: 1500,
        deductibleMet: 20,
        benefitsUsed: 125.5,
      })]);
    });

    it('posts only persisted policy fields', async () => {
      server.use(http.post('/api/v1/insurance/patients/p-1/policies', async ({ request }) => {
        expect(await request.json()).toEqual({
          carrier_id: 'car-1',
          subscriber_id: 'SUB-NEW',
          relationship_to_subscriber: 'self',
          is_primary: true,
          annual_maximum: 2000,
          effective_date: '2026-01-01',
        });
        return HttpResponse.json({
          ...policyWire,
          id: 'pol-2',
          subscriber_id: 'SUB-NEW',
          annual_maximum: '2000.00',
        });
      }));

      const result = await insuranceApi.addPatientInsurance('p-1', {
        carrierId: 'car-1',
        subscriberId: 'SUB-NEW',
        relationshipToSubscriber: 'self',
        isPrimary: true,
        annualMaximum: 2000,
        effectiveDate: '2026-01-01',
      });

      expect(result).toEqual(expect.objectContaining({ id: 'pol-2', annualMaximum: 2000 }));
    });

    it('uses the implemented policy delete route', async () => {
      server.use(http.delete('/api/v1/insurance/policies/pol-1', () =>
        HttpResponse.json({ message: 'Insurance policy deleted successfully' }),
      ));

      await expect(insuranceApi.deleteInsurancePolicy('pol-1')).resolves.toBeUndefined();
    });
  });

  describe('claims', () => {
    it('preserves pagination metadata and converts Decimal strings', async () => {
      server.use(http.get('/api/v1/insurance/claims/', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('patient_id')).toBe('p-1');
        expect(url.searchParams.get('start_date')).toBe('2026-01-01');
        expect(url.searchParams.get('limit')).toBe('25');
        expect(url.searchParams.get('offset')).toBe('25');
        return HttpResponse.json({ claims: [claimWire], count: 1, total: 51, limit: 25, offset: 25, next_offset: 50 });
      }));

      const result = await insuranceApi.getClaims({ patientId: 'p-1', startDate: '2026-01-01', limit: 25, offset: 25 });

      expect(result).toEqual(expect.objectContaining({ count: 1, total: 51, limit: 25, offset: 25, nextOffset: 50 }));
      expect(result.items[0]).toEqual(expect.objectContaining({
        patientInsuranceId: 'pol-1',
        billedAmount: 120,
        paidAmount: 0,
        outstandingBalance: 120,
        procedureCodes: [{ code: 'D1110', description: 'Cleaning', fee: 120 }],
      }));
    });

    it('posts a valid backend claim payload', async () => {
      server.use(http.post('/api/v1/insurance/claims/', async ({ request }) => {
        expect(await request.json()).toEqual({
          patient_insurance_id: 'pol-1',
          service_date: '2026-06-01',
          billed_amount: 120,
          procedure_codes: [{ code: 'D1110', description: 'Cleaning', fee: 120 }],
          diagnosis_codes: ['K02.9'],
          notes: 'Initial claim',
        });
        return HttpResponse.json({ ...claimWire, id: 'cl-2', notes: 'Initial claim' });
      }));

      const result = await insuranceApi.createClaim({
        patientInsuranceId: 'pol-1',
        serviceDate: '2026-06-01',
        billedAmount: 120,
        procedureCodes: [{ code: 'D1110', description: 'Cleaning', fee: 120 }],
        diagnosisCodes: ['K02.9'],
        notes: 'Initial claim',
      });

      expect(result.id).toBe('cl-2');
    });

    it('maps update and submit responses using the backend status vocabulary', async () => {
      server.use(
        http.put('/api/v1/insurance/claims/cl-1', async ({ request }) => {
          expect(await request.json()).toEqual({ status: 'in_review', allowed_amount: 100 });
          return HttpResponse.json({ ...claimWire, status: 'in_review', allowed_amount: '100.00' });
        }),
        http.post('/api/v1/insurance/claims/cl-1/submit', () =>
          HttpResponse.json({ ...claimWire, status: 'submitted', submission_date: '2026-06-02' }),
        ),
      );

      await expect(insuranceApi.updateClaim('cl-1', { status: 'in_review', allowedAmount: 100 })).resolves.toEqual(
        expect.objectContaining({ status: 'in_review', allowedAmount: 100 }),
      );
      await expect(insuranceApi.submitClaim('cl-1')).resolves.toEqual(
        expect.objectContaining({ status: 'submitted', submissionDate: '2026-06-02' }),
      );
    });
  });

  describe('pre-authorizations', () => {
    it('maps the paginated envelope, procedure codes, and Decimal strings', async () => {
      server.use(http.get('/api/v1/insurance/pre-auth/', () =>
        HttpResponse.json({ pre_authorizations: [preAuthWire], count: 1, total: 1, limit: 50, offset: 0, next_offset: null }),
      ));

      const result = await insuranceApi.getPreAuthorizations();

      expect(result.nextOffset).toBeNull();
      expect(result.items[0]).toEqual(expect.objectContaining({
        patientInsuranceId: 'pol-1',
        authorizationNumber: 'PA-20260601-ABC12345',
        estimatedCost: 120,
        procedureCodes: [{ code: 'D1110', description: 'Cleaning', fee: 120 }],
      }));
    });

    it('posts a complete pre-authorization payload', async () => {
      server.use(http.post('/api/v1/insurance/pre-auth/', async ({ request }) => {
        expect(await request.json()).toEqual({
          patient_insurance_id: 'pol-1',
          request_date: '2026-06-01',
          procedure_codes: [{ code: 'D1110', description: 'Cleaning', fee: 120 }],
          estimated_cost: 120,
          notes: 'Review requested',
        });
        return HttpResponse.json({ ...preAuthWire, id: 'pa-2', notes: 'Review requested' });
      }));

      const result = await insuranceApi.createPreAuthorization({
        patientInsuranceId: 'pol-1',
        requestDate: '2026-06-01',
        procedureCodes: [{ code: 'D1110', description: 'Cleaning', fee: 120 }],
        estimatedCost: 120,
        notes: 'Review requested',
      });

      expect(result.id).toBe('pa-2');
    });

    it('uses only supported status values in updates', async () => {
      server.use(http.put('/api/v1/insurance/pre-auth/pa-1', async ({ request }) => {
        expect(await request.json()).toEqual({ status: 'approved', approved_amount: 100 });
        return HttpResponse.json({ ...preAuthWire, status: 'approved', approved_amount: '100.00' });
      }));

      await expect(insuranceApi.updatePreAuthorization('pa-1', { status: 'approved', approvedAmount: 100 })).resolves.toEqual(
        expect.objectContaining({ status: 'approved', approvedAmount: 100 }),
      );
    });
  });
});
