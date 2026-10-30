# Setup Guide

Quick setup guide for CoreDent development environment.

## Prerequisites

- Node.js 18+ and npm
- Git
- Code editor (VS Code recommended)

## Quick Start

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd coredent-style-main

# 2. Install dependencies
npm install

# 3. Copy environment variables
cp .env.example .env

# 4. Start development server
npm run dev
```

The app will be available at `http://localhost:8080`

## Development Commands

```bash
# Development
npm run dev              # Start dev server
npm run build            # Build for production
npm run preview          # Preview production build

# Testing
npm test                 # Run tests
npm run test:watch       # Watch mode
npm test -- --coverage   # With coverage

# Code Quality
npm run lint             # Run ESLint
npm run typecheck        # TypeScript check
```

## Environment Variables

Create a `.env` file in the root directory:

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:3000/api

# Environment
VITE_ENV=development

# Feature Flags
VITE_ENABLE_DEMO_MODE=true
VITE_ENABLE_ANALYTICS=false
```

## Demo Credentials

For development/testing:
- Email: `demo@coredent.com`
- Password: `demo123`

## VS Code Setup

Recommended extensions:
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- TypeScript Vue Plugin (Volar)

Create `.vscode/settings.json`:
```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.tsdk": "node_modules/typescript/lib"
}
```

## Docker Setup

```bash
# Build image
docker build -t coredent:latest .

# Run container
docker run -p 8080:80 coredent:latest

# Or use docker-compose
docker-compose up -d
```

## Troubleshooting

### Port already in use
```bash
# Change port in vite.config.ts or:
npm run dev -- --port 3000
```

### Module not found
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

### TypeScript errors
```bash
# Run type checking
npm run typecheck
```

### Test failures
```bash
# Clear test cache
npm test -- --clearCache
```

## Next Steps

1. Read [ARCHITECTURE.md](./ARCHITECTURE.md) for technical overview
2. Review [CONTRIBUTING.md](./CONTRIBUTING.md) for development guidelines
3. Check [API.md](./API.md) for API documentation
4. See [ACCESSIBILITY.md](./ACCESSIBILITY.md) for accessibility guidelines

## Getting Help

- Documentation: See docs in root directory
- Issues: Open a GitHub issue
- Email: dev@coredent.com

---

Happy coding! 🦷
