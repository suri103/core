import { describe, it, expect, beforeEach } from 'vitest';
import { authApi } from '../api';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';

describe('authApi', () => {
  beforeEach(() => {
    // Reset any runtime request handlers we may add during tests
    server.resetHandlers();
  });

  describe('login', () => {
    it('should login successfully with valid credentials', async () => {
      const result = await authApi.login({
        email: 'demo@coredent.com',
        password: 'demo123',
      });

      expect(result.success).toBe(true);
      expect(result.data).toHaveProperty('access_token');
      expect(result.data).toHaveProperty('refresh_token');
    });

    it('should handle login failure with invalid credentials', async () => {
      const result = await authApi.login({
        email: 'test@example.com',
        password: 'wrongpassword',
      });

      expect(result.success).toBe(false);
      expect(result.error?.message).toBe('Invalid credentials');
    });

    it('should handle network errors', async () => {
      server.use(
        http.post('/api/v1/auth/login', () => {
          return HttpResponse.error();
        })
      );

      const result = await authApi.login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(result.success).toBe(false);
    });
  });

  describe('getCurrentUser', () => {
    it('should get current user successfully', async () => {
      const result = await authApi.getCurrentUser();

      expect(result.success).toBe(true);
      expect(result.data).toHaveProperty('id');
      expect(result.data).toHaveProperty('email');
      expect(result.data).toHaveProperty('role');
    });

    it('should handle unauthorized access', async () => {
      server.use(
        http.get('/api/v1/auth/me', () => {
          return HttpResponse.json(
            { message: 'Unauthorized' },
            { status: 401 }
          );
        })
      );

      const result = await authApi.getCurrentUser();

      expect(result.success).toBe(false);
    });
  });
});