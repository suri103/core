# 🚀 Vercel Deployment Guide for CoreDent Frontend

## Prerequisites
- Vercel account (sign up at https://vercel.com)
- Your custom .com domain
- Backend API URL from Railway

## Step 1: Install Vercel CLI (Optional)
```bash
npm install -g vercel
```

## Step 2: Deploy via Vercel Dashboard (Recommended)

### A. Connect GitHub Repository
1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your GitHub repository: `suraiamkapooram10008-lgtm/coredentist`
4. Configure project:
   - **Framework Preset**: Vite
   - **Root Directory**: `coredent-style-main`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

### B. Set Environment Variables
In Vercel project settings, add:

```bash
VITE_API_URL=https://your-backend.railway.app
```

Replace `your-backend.railway.app` with your actual Railway backend URL.

### C. Deploy
Click "Deploy" - Vercel will build and deploy automatically.

## Step 3: Add Custom Domain

### A. In Vercel Dashboard
1. Go to your project → Settings → Domains
2. Add your custom domain (e.g., `coredent.com` or `www.coredent.com`)
3. Vercel will provide DNS records

### B. Configure DNS
Add these records to your domain registrar:

**For root domain (coredent.com):**
```
Type: A
Name: @
Value: 76.76.21.21
```

**For www subdomain:**
```
Type: CNAME
Name: www
Value: cname.vercel-dns.com
```

**SSL Certificate:**
Vercel automatically provisions SSL certificates via Let's Encrypt.

## Step 4: Update Backend CORS

After deployment, update your Railway backend environment variable:

```bash
CORS_ORIGINS=https://coredent.com,https://www.coredent.com,https://your-vercel-app.vercel.app
```

Then redeploy the backend in Railway.

## Step 5: Verify Deployment

1. Visit your domain: `https://coredent.com`
2. Check browser console for errors
3. Test login functionality
4. Verify API calls are working

## Alternative: Deploy via CLI

```bash
cd coredent-style-main
vercel login
vercel --prod
```

Follow the prompts to configure your project.

## Automatic Deployments

Vercel automatically deploys:
- **Production**: Every push to `main` or `master` branch
- **Preview**: Every pull request

## Environment Variables for Different Environments

### Production
```bash
VITE_API_URL=https://api.coredent.com
```

### Preview/Staging
```bash
VITE_API_URL=https://your-backend-staging.railway.app
```

## Troubleshooting

### Issue: 404 on page refresh
**Solution**: Already configured in `vercel.json` with rewrites

### Issue: API calls failing
**Solution**: 
1. Check CORS_ORIGINS in Railway backend
2. Verify VITE_API_URL in Vercel environment variables
3. Check browser console for CORS errors

### Issue: Service Worker not loading
**Solution**: Already configured in `vercel.json` with proper headers

### Issue: Build fails
**Solution**:
1. Check build logs in Vercel dashboard
2. Verify all dependencies are in `package.json`
3. Ensure Node version compatibility (use Node 18+)

## Performance Optimization

Vercel automatically provides:
- ✅ Global CDN
- ✅ Edge caching
- ✅ Automatic compression (Brotli/Gzip)
- ✅ Image optimization
- ✅ HTTP/2 & HTTP/3

## Monitoring

Access analytics in Vercel dashboard:
- Page views
- Performance metrics
- Error tracking
- Real User Monitoring (RUM)

## Custom Domain SSL

Vercel automatically:
- Provisions SSL certificates
- Renews certificates before expiry
- Redirects HTTP to HTTPS
- Supports HSTS

## Next Steps

1. ✅ Deploy to Vercel
2. ✅ Add custom domain
3. ✅ Update backend CORS
4. ✅ Test end-to-end
5. Set up monitoring alerts
6. Configure custom error pages (optional)
7. Enable Web Analytics (optional)

## Support

- Vercel Docs: https://vercel.com/docs
- Vercel Support: https://vercel.com/support
- Community: https://github.com/vercel/vercel/discussions

---

Your CoreDent frontend will be live on your custom domain with automatic HTTPS, global CDN, and continuous deployment! 🎉
