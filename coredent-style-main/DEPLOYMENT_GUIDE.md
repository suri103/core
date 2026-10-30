# CoreDent PMS - Deployment Guide

## Complete Production Deployment Instructions

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Setup](#environment-setup)
3. [Build Process](#build-process)
4. [Deployment Methods](#deployment-methods)
5. [Post-Deployment](#post-deployment)
6. [Monitoring](#monitoring)
7. [Rollback Procedures](#rollback-procedures)
8. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### Required Software
- [ ] Node.js 18+ installed
- [ ] npm 9+ installed
- [ ] Git installed
- [ ] Docker installed (for containerized deployment)
- [ ] SSL certificates obtained

### Configuration Files
- [ ] `.env.production` configured with production values
- [ ] `nginx.conf` updated with production domain
- [ ] SSL certificates placed in `ssl/` directory
- [ ] Backend API URL configured
- [ ] Sentry DSN configured

### Code Quality
- [ ] All tests passing (`npm test`)
- [ ] Linting passing (`npm run lint`)
- [ ] Type checking passing (`npm run type-check`)
- [ ] E2E tests passing (`npm run test:e2e`)
- [ ] No console.logs in production code
- [ ] Security audit completed (`npm audit`)

### Security
- [ ] `.env` files not committed to git
- [ ] CSRF protection enabled
- [ ] CSP headers configured
- [ ] HTTPS enforced
- [ ] Security headers verified
- [ ] API authentication configured

---

## Environment Setup

### 1. Create Production Environment File

```bash
cp .env.production.example .env.production
```

Edit `.env.production` with your values:

```env
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_ENV=production
VITE_ENABLE_DEMO_MODE=false
VITE_DEV_BYPASS_AUTH=false
VITE_SENTRY_DSN=your-sentry-dsn
VITE_GA_MEASUREMENT_ID=your-ga-id
```

### 2. Configure Backend API

Ensure your backend API is:
- Running and accessible
- Configured to accept CORS from your domain
- Validating CSRF tokens
- Using HTTPS
- Rate limiting enabled

### 3. SSL Certificate Setup

Place your SSL certificates:
```bash
mkdir -p ssl
cp your-cert.crt ssl/
cp your-key.key ssl/
```

Update `nginx.conf`:
```nginx
ssl_certificate /etc/nginx/ssl/your-cert.crt;
ssl_certificate_key /etc/nginx/ssl/your-key.key;
```

---

## Build Process

### Automated Build (Recommended)

```bash
chmod +x deploy.sh
./deploy.sh production
```

The script will:
1. Verify Node.js version
2. Install dependencies
3. Run linting
4. Run type checking
5. Run tests
6. Create backup
7. Build for production
8. Verify build
9. Generate manifest

### Manual Build

```bash
# Install dependencies
npm ci --production=false

# Run quality checks
npm run lint
npm run type-check
npm test -- --run

# Build
npm run build

# Verify build
ls -la dist/
```

### Build Output

The build creates:
- `dist/` - Production-ready files
- `dist/index.html` - Entry point
- `dist/assets/` - JavaScript, CSS, images
- `dist/manifest.json` - Build metadata

---

## Deployment Methods

### Method 1: Docker Deployment (Recommended)

#### Build Docker Image

```bash
docker build -t coredent-pms:latest .
```

#### Run with Docker Compose

```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### Verify Container

```bash
docker ps
docker logs coredent-frontend
```

#### Access Application

```
http://localhost:80
https://localhost:443
```

---

### Method 2: Nginx Deployment

#### Install Nginx

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx
```

#### Deploy Files

```bash
# Copy build files
sudo cp -r dist/* /var/www/html/

# Copy nginx config
sudo cp nginx.conf /etc/nginx/sites-available/coredent
sudo ln -s /etc/nginx/sites-available/coredent /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

#### Enable HTTPS

```bash
# Using Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

### Method 3: Cloud Deployment

#### AWS S3 + CloudFront

```bash
# Install AWS CLI
pip install awscli

# Configure AWS
aws configure

# Sync to S3
aws s3 sync dist/ s3://your-bucket-name/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id YOUR_DIST_ID \
  --paths "/*"
```

#### Netlify

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy
netlify deploy --prod --dir=dist
```

#### Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel --prod
```

---

## Post-Deployment

### 1. Health Check

```bash
chmod +x healthcheck.sh
./healthcheck.sh https://yourdomain.com
```

### 2. Smoke Tests

Test critical user flows:
- [ ] Login/logout
- [ ] Dashboard loads
- [ ] Patient list loads
- [ ] Schedule view works
- [ ] Settings page accessible
- [ ] API calls successful

### 3. Performance Check

```bash
# Using Lighthouse
npm install -g lighthouse
lighthouse https://yourdomain.com --view
```

Target scores:
- Performance: 90+
- Accessibility: 95+
- Best Practices: 100
- SEO: 90+

### 4. Security Verification

```bash
# Check security headers
curl -I https://yourdomain.com | grep -E "X-Frame-Options|Content-Security-Policy|X-Content-Type-Options"

# SSL test
curl -I https://yourdomain.com | grep "HTTP/2"
```

### 5. Monitor Error Logs

Check Sentry dashboard for:
- JavaScript errors
- API errors
- Performance issues
- User feedback

---

## Monitoring

### Application Monitoring

#### Sentry Setup

1. Create Sentry project
2. Copy DSN to `.env.production`
3. Add to `index.html`:

```html
<script src="https://browser.sentry-cdn.com/7.x.x/bundle.min.js"></script>
<script>
  Sentry.init({
    dsn: 'YOUR_SENTRY_DSN',
    environment: 'production',
    tracesSampleRate: 0.1,
  });
</script>
```

#### Google Analytics

Add to `index.html`:

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_MEASUREMENT_ID');
</script>
```

### Server Monitoring

#### Nginx Logs

```bash
# Access logs
tail -f /var/log/nginx/access.log

# Error logs
tail -f /var/log/nginx/error.log
```

#### Docker Logs

```bash
docker logs -f coredent-frontend
```

### Uptime Monitoring

Set up monitoring with:
- UptimeRobot
- Pingdom
- StatusCake
- AWS CloudWatch

---

## Rollback Procedures

### Quick Rollback

```bash
# List backups
ls -la backups/

# Extract previous build
tar -xzf backups/build_TIMESTAMP.tar.gz

# Deploy previous version
sudo cp -r dist/* /var/www/html/
sudo systemctl restart nginx
```

### Docker Rollback

```bash
# List images
docker images

# Run previous version
docker run -d -p 80:80 coredent-pms:previous-tag
```

### Git Rollback

```bash
# Find previous commit
git log --oneline

# Revert to previous version
git revert HEAD
git push

# Rebuild and deploy
./deploy.sh production
```

---

## Troubleshooting

### Issue: White Screen

**Symptoms:** Application shows blank white screen

**Solutions:**
1. Check browser console for errors
2. Verify API URL is correct
3. Check CORS configuration
4. Verify build files are present
5. Check nginx error logs

```bash
# Check if files exist
ls -la /var/www/html/

# Check nginx errors
sudo tail -f /var/log/nginx/error.log
```

---

### Issue: API Calls Failing

**Symptoms:** Network errors, 404s, CORS errors

**Solutions:**
1. Verify API URL in `.env.production`
2. Check backend is running
3. Verify CORS headers on backend
4. Check network tab in browser DevTools

```bash
# Test API connectivity
curl https://api.yourdomain.com/health

# Check CORS
curl -H "Origin: https://yourdomain.com" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS https://api.yourdomain.com/api/endpoint
```

---

### Issue: SSL Certificate Errors

**Symptoms:** "Not Secure" warning, certificate errors

**Solutions:**
1. Verify certificate files are correct
2. Check certificate expiration
3. Verify domain matches certificate
4. Test SSL configuration

```bash
# Test SSL
openssl s_client -connect yourdomain.com:443

# Check certificate expiration
openssl x509 -in ssl/your-cert.crt -noout -dates
```

---

### Issue: Performance Issues

**Symptoms:** Slow page loads, high response times

**Solutions:**
1. Enable gzip compression
2. Verify CDN is working
3. Check bundle size
4. Enable caching headers
5. Optimize images

```bash
# Check gzip
curl -H "Accept-Encoding: gzip" -I https://yourdomain.com

# Check bundle size
du -sh dist/assets/*
```

---

### Issue: Authentication Not Working

**Symptoms:** Can't login, session expires immediately

**Solutions:**
1. Verify CSRF token configuration
2. Check cookie settings
3. Verify backend session management
4. Check browser console for errors

```bash
# Check CSRF token in requests
# Open browser DevTools > Network > Headers
```

---

## Maintenance

### Daily Tasks
- [ ] Check error logs in Sentry
- [ ] Monitor uptime status
- [ ] Review API response times
- [ ] Check failed authentication attempts

### Weekly Tasks
- [ ] Review security logs
- [ ] Check for dependency updates
- [ ] Monitor disk space
- [ ] Review performance metrics
- [ ] Backup database

### Monthly Tasks
- [ ] Security audit
- [ ] Dependency vulnerability scan
- [ ] Review and rotate secrets
- [ ] Update documentation
- [ ] Performance optimization review

---

## Support

### Getting Help

- Documentation: https://docs.coredent.com
- Support Email: support@coredent.com
- Emergency: emergency@coredent.com
- Status Page: https://status.coredent.com

### Reporting Issues

Include:
1. Environment (production/staging)
2. Browser and version
3. Steps to reproduce
4. Error messages
5. Screenshots
6. Network logs

---

## Appendix

### Useful Commands

```bash
# Check application version
curl https://yourdomain.com/manifest.json

# Test health endpoint
curl https://yourdomain.com/health

# Check nginx status
sudo systemctl status nginx

# Restart nginx
sudo systemctl restart nginx

# View Docker logs
docker logs coredent-frontend

# Check disk space
df -h

# Monitor system resources
htop
```

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| VITE_API_BASE_URL | Yes | Backend API URL |
| VITE_ENV | Yes | Environment name |
| VITE_SENTRY_DSN | Recommended | Sentry error tracking |
| VITE_GA_MEASUREMENT_ID | Optional | Google Analytics |
| VITE_ENABLE_DEMO_MODE | No | Demo mode flag |
| VITE_DEV_BYPASS_AUTH | No | Auth bypass (dev only) |

---

**Last Updated:** February 12, 2026
**Version:** 1.0.0
**Status:** Production Ready
