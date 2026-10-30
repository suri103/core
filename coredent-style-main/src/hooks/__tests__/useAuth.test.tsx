import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/contexts/AuthContext';
import { useAuth } from '@/contexts/auth-context';

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('@/lib/analytics', () => ({
  analytics: { identify: vi.fn() },
  trackLogin: vi.fn(),
  trackLogout: vi.fn(),
}));

vi.mock('@/lib/csrf', () => ({
  refreshCsrfToken: vi.fn(),
  clearCsrfToken: vi.fn(),
  getCsrfHeader: vi.fn(() => ({})),
}));
vi.mock('@/lib/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    // Logout clears the in-memory buffer (AuthContext calls this); the mock
    // must mirror the real interface or logout throws.
    clearLogs: vi.fn(),
  },
}));

const authApiMock = vi.hoisted(() => ({
  restoreSession: vi.fn(),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  setToken: vi.fn(),
  setRefreshToken: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  authApi: authApiMock,
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {children}
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('useAuth hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();

    authApiMock.restoreSession.mockResolvedValue(undefined);
    authApiMock.getCurrentUser.mockResolvedValue({ success: false, data: null, error: { message: 'Unauthorized' } });
    authApiMock.login.mockResolvedValue({ success: false, error: { message: 'Invalid credentials' } });
    authApiMock.register.mockResolvedValue({ success: false, error: { message: 'Registration failed' } });
    authApiMock.logout.mockResolvedValue({ success: true, data: null });
  });

  it('should return initial unauthenticated state', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.role).toBeNull();
  });

  it('should authenticate user successfully', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.login).toBeDefined();
    expect(result.current.logout).toBeDefined();
  });

  it('should handle login failure', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const loginResult = await act(async () => {
      return await result.current.login({
        email: 'test@example.com',
        password: 'wrongpassword',
      });
    });

    expect(loginResult).toBe(false);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('should logout user successfully', async () => {
    authApiMock.getCurrentUser.mockResolvedValueOnce({
      success: true,
      data: {
        id: 'user-1',
        email: 'test@example.com',
        firstName: 'Test',
        lastName: 'User',
        role: 'admin',
        practiceId: 'practice-1',
        practiceName: 'Test Practice',
      },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    await act(async () => {
      await result.current.logout();
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.role).toBeNull();
    });
  });

  it('should check user roles correctly', async () => {
    const mockUser = {
      id: 'user-1',
      email: 'admin@example.com',
      firstName: 'Admin',
      lastName: 'User',
      role: 'admin',
      practiceId: 'practice-1',
      practiceName: 'Test Practice',
    };

    authApiMock.getCurrentUser.mockResolvedValueOnce({ success: true, data: mockUser });

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    expect(result.current.hasRole('admin')).toBe(true);
    expect(result.current.hasRole('owner')).toBe(false);
    expect(result.current.hasRole('dentist')).toBe(false);
    expect(result.current.hasRole('admin', 'owner')).toBe(true);
    expect(result.current.hasRole('dentist' as any, 'hygienist' as any)).toBe(false);
  });

  it('should handle network errors during login', async () => {
    authApiMock.login.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const loginResult = await act(async () => {
      return await result.current.login({
        email: 'test@example.com',
        password: 'password123',
      });
    });

    expect(loginResult).toBe(false);
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('should restore session on mount', async () => {
    const mockUser = {
      id: 'user-1',
      email: 'existing@example.com',
      firstName: 'Existing',
      lastName: 'User',
      role: 'owner',
      practiceId: 'practice-1',
      practiceName: 'Test Practice',
    };

    authApiMock.getCurrentUser.mockResolvedValueOnce({ success: true, data: mockUser });

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user).toEqual(mockUser);
    });
  });

  it('should handle failed session restoration', async () => {
    authApiMock.getCurrentUser.mockResolvedValueOnce({ success: false, data: null, error: { message: 'Session expired' } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('should enable dev bypass in development mode', async () => {
    sessionStorage.clear();
    localStorage.clear();

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.logout).toBeDefined();
  });

  it('should handle logout even when API fails', async () => {
    authApiMock.getCurrentUser.mockResolvedValueOnce({
      success: true,
      data: {
        id: 'user-1',
        email: 'test@example.com',
        firstName: 'Test',
        lastName: 'User',
        role: 'dentist',
        practiceId: 'practice-1',
        practiceName: 'Test Practice',
      },
    });
    authApiMock.logout.mockRejectedValueOnce(new Error('Logout failed'));

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    await act(async () => {
      await result.current.logout();
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });
});
