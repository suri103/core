# Contributing to CoreDent

Thank you for your interest in contributing to CoreDent! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect differing viewpoints and experiences

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Git
- Code editor (VS Code recommended)

### Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/coredent.git
   cd coredent
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Create a branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running the App

```bash
npm run dev
```

### Running Tests

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# Coverage
npm test -- --coverage
```

### Linting

```bash
npm run lint
```

### Type Checking

```bash
npm run typecheck
```

## Coding Standards

### TypeScript

- Use TypeScript for all new code
- Define types in `src/types/`
- Avoid `any` - use `unknown` if type is truly unknown
- Use interfaces for object shapes
- Use type aliases for unions and primitives

**Good:**
```typescript
interface Patient {
  id: string;
  firstName: string;
  lastName: string;
}

type PatientStatus = 'active' | 'inactive';
```

**Bad:**
```typescript
const patient: any = { ... };
```

### React Components

- Use functional components with hooks
- One component per file
- Use named exports for components
- Props interface should be named `ComponentNameProps`

**Good:**
```typescript
interface PatientCardProps {
  patient: Patient;
  onSelect: (id: string) => void;
}

export function PatientCard({ patient, onSelect }: PatientCardProps) {
  return <div>...</div>;
}
```

### File Naming

- Components: PascalCase (`PatientCard.tsx`)
- Utilities: camelCase (`formatDate.ts`)
- Types: camelCase (`patient.ts`)
- Tests: `*.test.ts` or `*.test.tsx`

### Component Structure

```typescript
// 1. Imports
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import type { Patient } from '@/types/api';

// 2. Types
interface PatientCardProps {
  patient: Patient;
}

// 3. Component
export function PatientCard({ patient }: PatientCardProps) {
  // 3a. Hooks
  const [isExpanded, setIsExpanded] = useState(false);
  
  // 3b. Handlers
  const handleToggle = () => {
    setIsExpanded(!isExpanded);
  };
  
  // 3c. Render
  return (
    <div>
      <h3>{patient.firstName} {patient.lastName}</h3>
      <Button onClick={handleToggle}>Toggle</Button>
    </div>
  );
}
```

### Styling

- Use Tailwind CSS utility classes
- Follow mobile-first responsive design
- Use semantic color tokens (`primary`, `destructive`, etc.)
- Avoid inline styles

**Good:**
```tsx
<div className="flex items-center gap-4 p-4 rounded-lg bg-card">
```

**Bad:**
```tsx
<div style={{ display: 'flex', padding: '16px' }}>
```

### State Management

- Use `useState` for local component state
- Use TanStack Query for server state
- Use Context for global state (auth, theme)
- Use `useReducer` for complex state logic

### API Calls

- All API calls go through service layer
- Use TanStack Query hooks
- Handle loading and error states
- Show user-friendly error messages

**Good:**
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['patients', id],
  queryFn: () => patientsApi.getById(id),
});
```

## Testing Guidelines

### What to Test

- User interactions
- Edge cases and error states
- Accessibility
- Business logic
- API integration

### What Not to Test

- Implementation details
- Third-party libraries
- Trivial code

### Test Structure

```typescript
describe('PatientCard', () => {
  it('displays patient name', () => {
    // Arrange
    const patient = { id: '1', firstName: 'John', lastName: 'Doe' };
    
    // Act
    render(<PatientCard patient={patient} />);
    
    // Assert
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });
});
```

### Testing Best Practices

- Use `data-testid` sparingly - prefer accessible queries
- Test user behavior, not implementation
- Keep tests simple and focused
- Mock external dependencies
- Use `waitFor` for async operations

## Accessibility

- All interactive elements must be keyboard accessible
- Provide ARIA labels for icon-only buttons
- Ensure sufficient color contrast
- Test with screen readers
- Use semantic HTML

See [ACCESSIBILITY.md](./ACCESSIBILITY.md) for detailed guidelines.

## Git Workflow

### Commit Messages

Follow conventional commits:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(patients): add patient search functionality

fix(billing): correct invoice total calculation

docs(readme): update installation instructions

test(scheduling): add tests for appointment creation
```

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring

### Pull Request Process

1. Update your branch with latest main:
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. Run tests and linting:
   ```bash
   npm test
   npm run lint
   npm run typecheck
   ```

3. Push your branch:
   ```bash
   git push origin feature/your-feature
   ```

4. Create a pull request:
   - Use a clear, descriptive title
   - Reference related issues
   - Describe what changed and why
   - Include screenshots for UI changes
   - Add tests for new functionality

5. Address review feedback

6. Squash commits if requested

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Manual testing completed
- [ ] Accessibility tested

## Screenshots
(if applicable)

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Tests pass locally
```

## Code Review

### As a Reviewer

- Be kind and constructive
- Ask questions, don't demand changes
- Praise good solutions
- Suggest alternatives
- Focus on the code, not the person

### As an Author

- Don't take feedback personally
- Ask for clarification if needed
- Respond to all comments
- Thank reviewers for their time

## Documentation

- Update README.md for user-facing changes
- Update ARCHITECTURE.md for architectural changes
- Update API.md for API changes
- Add JSDoc comments for complex functions
- Include examples in documentation

## Performance

- Avoid unnecessary re-renders
- Use React.memo for expensive components
- Implement virtual scrolling for large lists
- Lazy load routes and components
- Optimize images and assets

## Security

- Never commit secrets or API keys
- Sanitize user input
- Use parameterized queries
- Implement proper authentication
- Follow OWASP guidelines

## Questions?

- Open an issue for bugs
- Start a discussion for questions
- Email: dev@coredent.com

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to CoreDent! 🦷
