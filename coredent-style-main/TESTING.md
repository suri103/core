# Testing Guide

Comprehensive testing guide for CoreDent PMS.

## Test Stack

- **Unit/Integration**: Vitest + React Testing Library
- **E2E**: Playwright
- **Accessibility**: axe-core/playwright
- **API Mocking**: MSW (Mock Service Worker)
- **Coverage**: Vitest Coverage (v8)

## Running Tests

### Unit Tests

```bash
# Run all unit tests
npm test

# Watch mode
npm run test:watch

# With coverage
npm run test:coverage
```

### E2E Tests

```bash
# Run E2E tests
npm run test:e2e

# Interactive UI mode
npm run test:e2e:ui

# Debug mode
npm run test:e2e:debug
```

## Test Structure

```
src/
├── components/
│   └── __tests__/          # Component tests
├── hooks/
│   └── __tests__/          # Hook tests
├── lib/
│   └── __tests__/          # Utility tests
├── services/
│   └── __tests__/          # Service tests
└── test/
    ├── setup.ts            # Test setup
    ├── test-utils.tsx      # Custom render utilities
    └── mocks/
        ├── handlers.ts     # MSW handlers
        └── server.ts       # MSW server

e2e/
├── auth.spec.ts            # Authentication flows
├── navigation.spec.ts      # Navigation tests
└── accessibility.spec.ts   # A11y tests
```

## Writing Tests

### Component Tests

```typescript
import { render, screen } from '@/test/test-utils';
import { PatientCard } from './PatientCard';

describe('PatientCard', () => {
  it('displays patient information', () => {
    const patient = createMockUser({ firstName: 'John', lastName: 'Doe' });
    
    render(<PatientCard patient={patient} onSelect={vi.fn()} />);
    
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });
});
```

### Hook Tests

```typescript
import { renderHook, act } from '@testing-library/react';
import { useScheduling } from './useScheduling';

describe('useScheduling', () => {
  it('navigates to next day', () => {
    const { result } = renderHook(() => useScheduling());
    
    act(() => {
      result.current.goToNext();
    });
    
    expect(result.current.currentDate).toBeDefined();
  });
});
```

### E2E Tests

```typescript
import { test, expect } from '@playwright/test';

test('user can login', async ({ page }) => {
  await page.goto('/login');
  
  await page.getByLabel(/email/i).fill('demo@coredent.com');
  await page.getByLabel(/password/i).fill('demo123');
  await page.getByRole('button', { name: /sign in/i }).click();
  
  await expect(page).toHaveURL(/\/dashboard/);
});
```

### Accessibility Tests

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('page has no accessibility violations', async ({ page }) => {
  await page.goto('/dashboard');
  
  const results = await new AxeBuilder({ page }).analyze();
  
  expect(results.violations).toEqual([]);
});
```

## Test Utilities

### Custom Render

```typescript
import { render } from '@/test/test-utils';

// Renders with all providers (Router, Query, Auth)
render(<MyComponent />, {
  user: createMockUser({ role: 'dentist' }),
  isAuthenticated: true,
});
```

### Mock Factories

```typescript
import { createMockUser } from '@/test/test-utils';

const user = createMockUser({
  role: 'dentist',
  firstName: 'Jane',
});
```

## Coverage Goals

- **Utilities**: 90%+
- **Hooks**: 80%+
- **Components**: 70%+
- **Services**: 85%+
- **Overall**: 75%+

## Best Practices

### Do's

✅ Test user behavior, not implementation
✅ Use accessible queries (getByRole, getByLabelText)
✅ Test error states and edge cases
✅ Mock external dependencies
✅ Keep tests simple and focused
✅ Use descriptive test names

### Don'ts

❌ Test implementation details
❌ Overuse data-testid
❌ Test third-party libraries
❌ Write brittle tests
❌ Ignore accessibility
❌ Skip error cases

## Debugging Tests

### Unit Tests

```bash
# Run specific test file
npm test -- src/components/PatientCard.test.tsx

# Run tests matching pattern
npm test -- --grep "PatientCard"

# Debug in VS Code
# Add breakpoint and use "Debug Test" in test file
```

### E2E Tests

```bash
# Debug mode with browser
npm run test:e2e:debug

# Run specific test
npx playwright test auth.spec.ts

# View test report
npx playwright show-report
```

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Pushes to main/develop
- Pre-commit hooks (lint + typecheck)

See `.github/workflows/ci.yml` for configuration.

## Troubleshooting

### Tests timing out

Increase timeout in test:
```typescript
test('slow test', async () => {
  // ...
}, { timeout: 10000 });
```

### MSW not intercepting requests

Check handlers are registered:
```typescript
import { server } from '@/test/mocks/server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Playwright browser issues

```bash
# Reinstall browsers
npx playwright install --with-deps
```

## Resources

- [Vitest Documentation](https://vitest.dev)
- [React Testing Library](https://testing-library.com/react)
- [Playwright Documentation](https://playwright.dev)
- [MSW Documentation](https://mswjs.io)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

---

Happy testing! 🧪
