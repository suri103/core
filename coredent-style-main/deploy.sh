#!/bin/bash

# CoreDent PMS Deployment Script
# Automates the deployment process with safety checks

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
BUILD_DIR="dist"
BACKUP_DIR="backups"

echo -e "${GREEN}CoreDent PMS Deployment Script${NC}"
echo "Environment: $ENVIRONMENT"
echo "-----------------------------------"

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed"
    exit 1
fi
print_success "Node.js is installed"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    print_error "npm is not installed"
    exit 1
fi
print_success "npm is installed"

# Check Node version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    print_error "Node.js version must be 18 or higher (current: $(node -v))"
    exit 1
fi
print_success "Node.js version is compatible"

# Check if .env file exists
if [ ! -f ".env.$ENVIRONMENT" ] && [ "$ENVIRONMENT" != "development" ]; then
    print_warning ".env.$ENVIRONMENT file not found, using .env"
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
npm ci --production=false
print_success "Dependencies installed"

# Run linting
echo ""
echo "Running linter..."
npm run lint || {
    print_error "Linting failed"
    exit 1
}
print_success "Linting passed"

# Run type checking
echo ""
echo "Running type check..."
npm run type-check || {
    print_error "Type checking failed"
    exit 1
}
print_success "Type checking passed"

# Run tests
echo ""
echo "Running tests..."
npm test -- --run || {
    print_error "Tests failed"
    exit 1
}
print_success "Tests passed"

# Create backup of current build
if [ -d "$BUILD_DIR" ]; then
    echo ""
    echo "Creating backup..."
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_DIR"
    tar -czf "$BACKUP_DIR/build_$TIMESTAMP.tar.gz" "$BUILD_DIR"
    print_success "Backup created: $BACKUP_DIR/build_$TIMESTAMP.tar.gz"
fi

# Build for production
echo ""
echo "Building for $ENVIRONMENT..."
if [ "$ENVIRONMENT" = "production" ]; then
    npm run build
else
    npm run build -- --mode $ENVIRONMENT
fi
print_success "Build completed"

# Check build size
BUILD_SIZE=$(du -sh "$BUILD_DIR" | cut -f1)
echo "Build size: $BUILD_SIZE"

# Verify critical files exist
echo ""
echo "Verifying build..."
CRITICAL_FILES=("$BUILD_DIR/index.html" "$BUILD_DIR/assets")
for file in "${CRITICAL_FILES[@]}"; do
    if [ ! -e "$file" ]; then
        print_error "Critical file missing: $file"
        exit 1
    fi
done
print_success "Build verification passed"

# Security check - ensure no .env files in build
if find "$BUILD_DIR" -name ".env*" | grep -q .; then
    print_error "Environment files found in build directory!"
    exit 1
fi
print_success "Security check passed"

# Generate build manifest
echo ""
echo "Generating build manifest..."
cat > "$BUILD_DIR/manifest.json" << EOF
{
  "version": "$(node -p "require('./package.json').version")",
  "buildTime": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "environment": "$ENVIRONMENT",
  "nodeVersion": "$(node -v)",
  "gitCommit": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
  "gitBranch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
}
EOF
print_success "Build manifest created"

# Deployment summary
echo ""
echo "-----------------------------------"
echo -e "${GREEN}Deployment Ready!${NC}"
echo "Environment: $ENVIRONMENT"
echo "Build directory: $BUILD_DIR"
echo "Build size: $BUILD_SIZE"
echo ""
echo "Next steps:"
echo "1. Review the build in $BUILD_DIR"
echo "2. Deploy to your hosting service"
echo "3. Run smoke tests"
echo "4. Monitor error logs"
echo ""
echo "Deployment commands:"
echo "  Docker: docker build -t coredent-pms ."
echo "  Nginx: sudo cp -r $BUILD_DIR/* /var/www/html/"
echo "  S3: aws s3 sync $BUILD_DIR s3://your-bucket/"
echo ""
print_success "Deployment preparation complete!"
