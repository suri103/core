@echo off
REM CoreDent Improvements Setup Script for Windows
REM This script installs all new dependencies and sets up the development environment

echo.
echo 🚀 Setting up CoreDent improvements...
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Node.js is not installed. Please install Node.js 18+ first.
    exit /b 1
)

echo ✅ Node.js version:
node --version
echo.

REM Install dependencies
echo 📦 Installing dependencies...
call npm install

REM Install new dependencies
echo 📦 Installing new dependencies...
call npm install --save web-vitals@^4.2.4
call npm install --save-dev @axe-core/playwright@^4.10.2 @playwright/test@^1.49.1 @vitest/coverage-v8@^3.2.4 husky@^9.1.7 prettier@^3.4.2 prettier-plugin-tailwindcss@^0.6.11

REM Setup Husky
echo 🪝 Setting up Husky pre-commit hooks...
call npm run prepare

REM Install Playwright browsers
echo 🎭 Installing Playwright browsers...
call npx playwright install --with-deps

REM Format existing code
echo ✨ Formatting code...
call npm run format

REM Run type check
echo 🔍 Running TypeScript type check...
call npm run typecheck

REM Run tests
echo 🧪 Running tests...
call npm test

echo.
echo ✅ Setup complete!
echo.
echo 📝 Next steps:
echo   1. Review any type errors: npm run typecheck
echo   2. Fix any failing tests: npm test
echo   3. Run E2E tests: npm run test:e2e
echo   4. Check formatting: npm run format:check
echo.
echo 📚 Documentation:
echo   - TESTING.md - Testing guide
echo   - IMPROVEMENTS.md - All improvements made
echo   - README.md - Project overview
echo.
echo 🎉 Happy coding!
pause
