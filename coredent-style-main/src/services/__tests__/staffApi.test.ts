import { describe, it, expect, beforeEach } from 'vitest';
import { staffApi } from '../staffApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type { StaffMember, StaffInvitation } from '@/types/staff';
const mockStaff: StaffMember = {
  id: 'staff-1',
  firstName: 'Jane',
  lastName: 'Doe',
  email: 'jane@example.com',
  role: 'dentist',
  status: 'active',
  avatarUrl: 'https://example.com/avatar.png',
  lastLoginAt: '2026-01-01T00:00:00Z',
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
};

const mockInvitation: StaffInvitation = {
  id: 'inv-1',
  email: 'newstaff@example.com',
  firstName: 'New',
  lastName: 'Hire',
  role: 'hygienist',
  invitedByName: 'Owner',
  expiresAt: '2026-07-01T00:00:00Z',
  createdAt: '2026-06-01T00:00:00Z',
};

describe('staffApi', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  describe('list', () => {
    it('returns paginated staff members', async () => {
      server.use(
        http.get('/api/v1/staff', () =>
          HttpResponse.json({
            data: [mockStaff],
            total: 1,
            page: 1,
            limit: 10,
            totalPages: 1,
          }),
        ),
      );

      const result = await staffApi.list();

      expect(result.success).toBe(true);
      expect(result.data?.data).toEqual([mockStaff]);
      expect(result.data?.total).toBe(1);
    });

    it('normalizes a bare backend array (List[UserResponse]) into the paginated envelope', async () => {
      server.use(
        http.get('/api/v1/staff', () =>
          HttpResponse.json([
            { id: 's1', first_name: 'Jane', last_name: 'Doe', email: 'j@x.com', role: 'dentist', is_active: true },
            { id: 's2', first_name: 'Bob', last_name: 'Smith', email: 'b@x.com', role: 'owner', is_active: false },
          ]),
        ),
      );

      const result = await staffApi.list();

      expect(result.success).toBe(true);
      expect(Array.isArray(result.data?.data)).toBe(true);
      expect(result.data?.data?.length).toBe(2);
      expect(result.data?.total).toBe(2);
      // is_active (bool) is mapped onto the frontend status contract.
      expect(result.data?.data?.[0].status).toBe('active');
      expect(result.data?.data?.[1].status).toBe('inactive');
      expect(result.data?.data?.[0].firstName).toBe('Jane');
    });

    it('returns empty data with total=0 when no staff', async () => {
      server.use(
        http.get('/api/v1/staff', () =>
          HttpResponse.json({ data: [], total: 0, page: 1, limit: 10, totalPages: 0 }),
        ),
      );

      const result = await staffApi.list();
      expect(result.success).toBe(true);
      expect(result.data?.data).toEqual([]);
      expect(result.data?.total).toBe(0);
    });

    it('surfaces server errors', async () => {
      server.use(
        http.get('/api/v1/staff', () =>
          HttpResponse.json({ message: 'Forbidden' }, { status: 403 }),
        ),
      );

      const result = await staffApi.list();
      expect(result.success).toBe(false);
      expect(result.error?.message).toMatch(/permission|forbidden/i);
    });
  });

  describe('listInvitations', () => {
    it('returns invitation list', async () => {
      server.use(
        http.get('/api/v1/staff/invitations', () => HttpResponse.json([mockInvitation])),
      );

      const result = await staffApi.listInvitations();
      expect(result.success).toBe(true);
      expect(result.data).toEqual([mockInvitation]);
    });

    it('returns empty list when no pending invitations', async () => {
      server.use(
        http.get('/api/v1/staff/invitations', () => HttpResponse.json([])),
      );

      const result = await staffApi.listInvitations();
      expect(result.success).toBe(true);
      expect(result.data).toEqual([]);
    });
  });

  describe('invite', () => {
    it('sends invitation and returns the new invitation record', async () => {
      server.use(
        http.post('/api/v1/staff/invitations', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockInvitation, ...body }, { status: 201 });
        }),
      );

      const result = await staffApi.invite({
        email: 'newstaff@example.com',
        firstName: 'New',
        lastName: 'Hire',
        role: 'hygienist',
      });

      expect(result.success).toBe(true);
      expect(result.data?.email).toBe('newstaff@example.com');
    });

    it('handles a 409 duplicate-email error', async () => {
      server.use(
        http.post('/api/v1/staff/invitations', () =>
          HttpResponse.json(
            { message: 'An invitation already exists for this email' },
            { status: 409 },
          ),
        ),
      );

      const result = await staffApi.invite({
        email: 'dup@example.com',
        firstName: 'Dup',
        lastName: 'User',
        role: 'dentist',
      });
      expect(result.success).toBe(false);
      expect(result.error?.message).toContain('already exists');
    });
  });

  describe('cancelInvitation', () => {
    it('cancels a pending invitation', async () => {
      server.use(
        http.delete('/api/v1/staff/invitations/inv-1', () =>
          HttpResponse.json({ message: 'Invitation cancelled' }),
        ),
      );

      const result = await staffApi.cancelInvitation('inv-1');
      expect(result.success).toBe(true);
    });
  });

  describe('getById', () => {
    it('returns a staff member by ID', async () => {
      server.use(
        http.get('/api/v1/staff/staff-1', () => HttpResponse.json(mockStaff)),
      );

      const result = await staffApi.getById('staff-1');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockStaff);
    });
  });

  describe('update', () => {
    it('updates staff details', async () => {
      server.use(
        http.put('/api/v1/staff/staff-1', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockStaff, ...body });
        }),
      );

      const result = await staffApi.update('staff-1', { firstName: 'Janet' });
      expect(result.success).toBe(true);
      expect(result.data?.firstName).toBe('Janet');
    });
  });

  describe('deactivate / reactivate', () => {
    it('deactivates a staff member', async () => {
      server.use(
        http.put('/api/v1/staff/staff-1/deactivate', () =>
          HttpResponse.json({ ...mockStaff, status: 'inactive' }),
        ),
      );

      const result = await staffApi.deactivate('staff-1');
      expect(result.success).toBe(true);
      expect(result.data?.status).toBe('inactive');
    });

    it('reactivates a staff member', async () => {
      server.use(
        http.put('/api/v1/staff/staff-1/reactivate', () =>
          HttpResponse.json({ ...mockStaff, status: 'active' }),
        ),
      );

      const result = await staffApi.reactivate('staff-1');
      expect(result.success).toBe(true);
      expect(result.data?.status).toBe('active');
    });
  });

  describe('resendInvitation', () => {
    it('resends a pending invitation', async () => {
      server.use(
        http.post('/api/v1/staff/invitations/inv-1/resend', () =>
          HttpResponse.json(mockInvitation),
        ),
      );

      const result = await staffApi.resendInvitation('inv-1');
      expect(result.success).toBe(true);
      expect(result.data?.id).toBe('inv-1');
    });
  });
});
