# Architecture Documentation

## Overview

CoreDent is a single-page application (SPA) built with React and TypeScript, following modern web development best practices.

## Technology Stack

### Frontend
- **React 18** - UI library with concurrent features
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tool and dev server
- **TanStack Query** - Server state management
- **React Router v6** - Client-side routing
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - Accessible component library built on Radix UI

### Development Tools
- **Vitest** - Unit testing framework
- **React Testing Library** - Component testing
- **ESLint** - Code linting
- **MSW** - API mocking for tests

## Project Structure

```
src/
├── components/          # React components
│   ├── admin/          # Admin-specific components
│   ├── auth/           # Authentication components
│   ├── billing/        # Billing & invoicing
│   ├── chart/          # Dental charting
│   ├── layout/         # Layout components
│   ├── patients/       # Patient management
│   ├── reports/        # Reporting
│   ├── scheduling/     # Appointment scheduling
│   ├── settings/       # Settings
│   ├── treatment/      # Treatment planning
│   └── ui/             # Base UI components
├── contexts/           # React contexts
│   └── AuthContext.tsx # Authentication state
├── hooks/              # Custom React hooks
│   ├── useScheduling.ts
│   └── use-toast.ts
├── lib/                # Utility functions
│   ├── utils.ts        # General utilities
│   ├── logger.ts       # Logging system
│   ├── errorHandler.ts # Error handling
│   └── accessibility.ts # A11y helpers
├── pages/              # Page components
│   ├── Dashboard.tsx
│   ├── Schedule.tsx
│   ├── Billing.tsx
│   └── ...
├── services/           # API service layer
│   ├── api.ts          # Core API client
│   ├── schedulingApi.ts
│   ├── billingApi.ts
│   └── ...
├── test/               # Test utilities
│   ├── setup.ts
│   ├── test-utils.tsx
│   └── mocks/
├── types/              # TypeScript definitions
│   ├── api.ts
│   ├── scheduling.ts
│   ├── billing.ts
│   └── ...
├── App.tsx             # Root component
└── main.tsx            # Entry point
```

## Architecture Patterns

### Component Architecture

Components follow a hierarchical structure:

1. **Pages** - Top-level route components
2. **Feature Components** - Domain-specific components
3. **UI Components** - Reusable, generic components

### State Management

- **Server State**: TanStack Query for API data
- **Client State**: React hooks (useState, useReducer)
- **Global State**: React Context for auth and theme
- **Form State**: React Hook Form

### Data Flow

```
User Action → Component → Service Layer → API → Backend
                ↓
            TanStack Query Cache
                ↓
            Component Re-render
```

## Key Design Decisions

### 1. Service Layer Pattern

All API calls go through a centralized service layer (`src/services/`):

**Benefits:**
- Single source of truth for API endpoints
- Easy to mock for testing
- Consistent error handling
- Type-safe API responses

**Example:**
```typescript
// services/api.ts
export const patientsApi = {
  list: (params) => apiClient.get('/patients', params),
  getById: (id) => apiClient.get(`/patients/${id}`),
  create: (data) => apiClient.post('/patients', data),
};
```

### 2. Type-First Development

All data structures are defined in `src/types/`:

**Benefits:**
- Compile-time type checking
- Better IDE autocomplete
- Self-documenting code
- Reduced runtime errors

### 3. Component Composition

Components use composition over inheritance:

**Benefits:**
- Flexible and reusable
- Easy to test
- Clear data flow
- Better separation of concerns

### 4. Lazy Loading

Pages are lazy-loaded for optimal performance:

```typescript
const Dashboard = lazy(() => import('./pages/Dashboard'));
```

**Benefits:**
- Smaller initial bundle
- Faster first paint
- Better code splitting

### 5. Error Boundaries

Global error boundary catches unhandled errors:

**Benefits:**
- Graceful error handling
- User-friendly error messages
- Error logging for debugging

## Authentication Flow

```
1. User enters credentials
2. AuthContext.login() called
3. API request to /auth/login
4. Token stored in sessionStorage
5. User object stored in context
6. Protected routes become accessible
7. API client includes token in headers
```

### Role-Based Access Control

```typescript
<ProtectedRoute allowedRoles={['owner', 'admin']}>
  <Settings />
</ProtectedRoute>
```

Roles:
- **Owner**: Full access
- **Admin**: Management functions
- **Dentist**: Clinical features
- **Front Desk**: Scheduling and basic billing

## API Integration

### API Client

Centralized HTTP client with:
- Token management
- Error handling
- Request/response interceptors
- Type-safe responses

### Response Format

```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}
```

### Error Handling

1. Network errors → Retry logic
2. 401 Unauthorized → Redirect to login
3. 403 Forbidden → Show access denied
4. 4xx/5xx → User-friendly error message

## Performance Optimizations

### 1. Code Splitting
- Route-based splitting
- Component lazy loading
- Dynamic imports

### 2. Caching Strategy
```typescript
{
  staleTime: 5 * 60 * 1000,  // 5 minutes
  gcTime: 10 * 60 * 1000,     // 10 minutes
  retry: 2,
}
```

### 3. Memoization
- React.memo for expensive components
- useMemo for computed values
- useCallback for stable functions

### 4. Virtual Scrolling
- Large lists use virtual scrolling
- Reduces DOM nodes
- Improves scroll performance

## Testing Strategy

### Unit Tests
- Pure functions
- Custom hooks
- Utility functions

### Component Tests
- User interactions
- Rendering logic
- Accessibility

### Integration Tests
- API integration
- Multi-component workflows
- End-to-end scenarios

### Test Coverage Goals
- Utilities: 90%+
- Components: 70%+
- Hooks: 80%+
- Services: 85%+

## Security Considerations

### 1. Authentication
- Session-based tokens
- Secure token storage
- Automatic token refresh
- Session timeout

### 2. Authorization
- Role-based access control
- Route protection
- API permission checks

### 3. Data Protection
- Input sanitization
- XSS prevention
- CSRF protection
- Secure headers

### 4. HIPAA Compliance
- Audit logging (planned)
- Data encryption (backend)
- Access controls
- Session management

## Deployment

### Build Process
```bash
npm run build
```

Output: `dist/` directory with optimized assets

### Environment Variables
```env
VITE_API_BASE_URL=https://api.coredent.com
VITE_ENV=production
```

### Hosting Options
- **Vercel**: Recommended for SPA
- **Netlify**: Alternative with CDN
- **AWS S3 + CloudFront**: Enterprise option
- **Docker**: Containerized deployment

## Monitoring & Observability

### Logging
- Centralized logger (`src/lib/logger.ts`)
- Log levels: debug, info, warn, error
- Production: Send to monitoring service

### Error Tracking
- Error boundary catches React errors
- Global error handlers for unhandled errors
- Integration ready for Sentry/LogRocket

### Performance Monitoring
- Web Vitals tracking
- API response times
- Component render times

## Future Enhancements

### Planned Features
- [ ] Real-time updates (WebSocket)
- [ ] Offline support (Service Worker)
- [ ] Progressive Web App (PWA)
- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Multi-language support (i18n)

### Technical Debt
- [ ] Increase test coverage to 80%
- [ ] Add E2E tests with Playwright
- [ ] Implement proper backend integration
- [ ] Add comprehensive API documentation
- [ ] Set up CI/CD pipeline

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development guidelines.

## Resources

- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [TanStack Query](https://tanstack.com/query/latest)
- [Tailwind CSS](https://tailwindcss.com)
- [Radix UI](https://www.radix-ui.com)

---

Last updated: February 2026
