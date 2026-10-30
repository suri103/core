import { createContext, useContext } from 'react';
import type { User, UserRole, LoginCredentials } from '@/types/api';

export interface RegisterData {
  practiceName: string;
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  country?: string;
  phone?: string;
}

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  role: UserRole | null;
  mustChangePassword: boolean;
  login: (credentials: LoginCredentials) => Promise<boolean>;
  register: (data: RegisterData) => Promise<boolean>;
  logout: () => Promise<void>;
  clearMustChangePassword: () => void;
  hasRole: (...roles: UserRole[]) => boolean;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
