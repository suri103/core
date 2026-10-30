#!/bin/bash

# CoreDent Improvements Setup Script
# This script installs all new dependencies and sets up the development environment

set -e

echo "🚀 Setting up CoreDent improvements..."
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

echo "✅ Node.js version: $(node --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Install new dependencies
echo "📦 Installing new dependencies..."
npm install --save web-vitals@^4.2.4
npm install --save-dev @axe-core/playwright@^4.10.2 @playwright/test@^1.49.1 @vitest/coverage-v8@^3.2.4 husky@^9.1.7 prettier@^3.4.2 prettier-plugin-tailwindcss@^0.6.11

# Setup Husky
echo "🪝 Setting up Husky pre-commit hooks..."
npm run prepare

# Install Playwright browsers
echo "🎭 Installing Playwright browsers..."
npx playwright install --with-deps

# Format existing code
echo "✨ Formatting code..."
npm run format || echo "⚠️  Some files may need manual formatting"

# Run type check
echo "🔍 Running TypeScript type check..."
npm run typecheck || echo "⚠️  Some type errors may need fixing"

# Run tests
echo "🧪 Running tests..."
npm test || echo "⚠️  Some tests may need updating"

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Review any type errors: npm run typecheck"
echo "  2. Fix any failing tests: npm test"
echo "  3. Run E2E tests: npm run test:e2e"
echo "  4. Check formatting: npm run format:check"
echo ""
echo "📚 Documentation:"
echo "  - TESTING.md - Testing guide"
echo "  - IMPROVEMENTS.md - All improvements made"
echo "  - README.md - Project overview"
echo ""
echo "🎉 Happy coding!"
