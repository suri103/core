# Multi-stage build for production
# Updated: 2026-03-24 - Fixed healthcheck and PWA config
# Force fresh build by including build timestamp file

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy build timestamp file FIRST (changes on every deploy)
COPY .build-timestamp ./

# Copy ALL source code
COPY . .

# Set build environment variables
ENV VITE_API_BASE_URL=https://coredentist-production.up.railway.app/api/v1
ENV VITE_ENABLE_DEMO_MODE=false
ENV VITE_DEBUG=false
ENV CI=true

# Install dependencies
RUN npm ci --ignore-scripts

# Build the application
RUN npm run build

# Verify build output
RUN ls -la dist/ && test -f dist/index.html

# Stage 2: Production
FROM nginx:alpine

# Install wget and curl for healthcheck
RUN apk add --no-cache wget curl

# Copy nginx config FIRST
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Verify files were copied
RUN ls -la /usr/share/nginx/html/ && \
    test -f /usr/share/nginx/html/index.html && \
    echo "✓ index.html found"

# Verify nginx config is valid
RUN nginx -t

# Expose port 8080 (Railway default)
EXPOSE 8080

# Health check for Railway monitoring
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
