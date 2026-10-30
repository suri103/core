# 🚀 Custom Domain Setup Guide - Vercel + Railway

Complete guide to set up your SaaS with a professional custom domain.

## 📋 Overview

**Final Setup:**
- Frontend: `app.yourdomain.com` (Vercel - FREE)
- Backend: `api.yourdomain.com` (Railway - $5-10/month)
- Database: Railway PostgreSQL (included)

**Total Cost:** ~$12/year (domain) + $5-10/month (Railway) = ~$72-132/year

---

## Step 1: Buy a Domain (15 minutes)

### Recommended Registrars

**Option A: Namecheap** (Easiest)
1. Go to https://www.namecheap.com
2. Search for your domain (e.g., `coredent.com`)
3. Add to cart and checkout (~$12/year)
4. Create account and complete purchase

**Option B: Cloudflare** (Best for advanced users)
1. Go to https://www.cloudflare.com/products/registrar/
2. Transfer or register domain (~$10/year)
3. Bonus: Free CDN and DDoS protection

**Option C: GoDaddy** (Most popular)
1. Go to https://www.godaddy.com
2. Search and buy domain (~$15/year)

**Domain Suggestions:**
- `coredent.com` (if available)
- `coredentpms.com`
- `mycoredent.com`
- `getcoredent.com`

---

## Step 2: Deploy Frontend to Vercel (10 minutes)

### 2.1 Create Vercel Account

1. Go to https://vercel.com
2. Sign up with GitHub (recommended)
3. Click "Add New Project"

### 2.2 Import Your Repository

**If using Git:**
1. Click "Import Git Repository"
2. Select your GitHub repo
3. Choose `coredent-style-main` folder as root directory

**If NOT using Git:**
1. Install Vercel CLI: `npm i -g vercel`
2. In `coredent-style-main` folder, run: `vercel`
3. Follow prompts to deploy

### 2.3 Configure Build Settings

In Vercel dashboard:

**Framework Preset:** Vite

**Build Command:**
```bash
npm run build
```

**Output Directory:**
```
dist
```

**Install Command:**
```bash
npm install
```

### 2.4 Add Environment Variables

In Vercel dashboard → Settings → Environment Variables:

```
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
VITE_ENABLE_DEMO_MODE=false
VITE_DEBUG=false
```

Replace `yourdomain.com` with your actual domain!

### 2.5 Deploy

Click "Deploy" and wait 2-3 minutes.

You'll get a URL like: `your-project.vercel.app`

---

## Step 3: Configure Custom Domain on Vercel (5 minutes)

### 3.1 Add Domain to Vercel

1. In Vercel dashboard → Settings → Domains
2. Click "Add Domain"
3. Enter: `app.yourdomain.com` (or just `yourdomain.com`)
4. Click "Add"

### 3.2 Configure DNS Records

Vercel will show you DNS records to add. Go to your domain registrar:

**For `app.yourdomain.com`:**

Add a CNAME record:
```
Type: CNAME
Name: app
Value: cname.vercel-dns.com
TTL: 3600 (or Auto)
```

**For root domain `yourdomain.com` (optional):**

Add A records:
```
Type: A
Name: @ (or leave blank)
Value: 76.76.21.21
TTL: 3600
```

### 3.3 Wait for DNS Propagation

- Usually takes 5-30 minutes
- Can take up to 48 hours in rare cases
- Check status in Vercel dashboard

---

## Step 4: Configure Custom Domain on Railway (5 minutes)

### 4.1 Add Domain to Railway Backend

1. Go to Railway dashboard
2. Open your backend service (coredentist-production)
3. Click "Settings" tab
4. Scroll to "Domains" section
5. Click "Generate Domain" or "Custom Domain"
6. Enter: `api.yourdomain.com`
7. Click "Add Domain"

### 4.2 Configure DNS Records

Railway will show you a CNAME record. Go to your domain registrar:

Add a CNAME record:
```
Type: CNAME
Name: api
Value: [Railway will provide this - looks like: xxx.up.railway.app]
TTL: 3600 (or Auto)
```

### 4.3 Wait for SSL Certificate

Railway automatically provisions SSL certificates (HTTPS).
This takes 1-5 minutes.

---

## Step 5: Update Backend Configuration (2 minutes)

### 5.1 Update CORS Origins

In Railway dashboard → Backend service → Variables:

Update or add:
```
CORS_ORIGINS=https://app.yourdomain.com,https://yourdomain.com
```

### 5.2 Update Frontend URL

Add this variable:
```
FRONTEND_URL=https://app.yourdomain.com
```

### 5.3 Redeploy Backend

Railway will automatically redeploy with new settings.

---

## Step 6: Update Frontend API URL (2 minutes)

### 6.1 Update Environment Variable

In Vercel dashboard → Settings → Environment Variables:

Update:
```
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
```

### 6.2 Redeploy Frontend

In Vercel dashboard → Deployments → Click "Redeploy"

---

## Step 7: Test Your Application (5 minutes)

### 7.1 Access Your Application

Open: `https://app.yourdomain.com` (or `https://yourdomain.com`)

### 7.2 Test Login

Login with:
- Email: `admin@coredent.com`
- Password: `Admin123!`

### 7.3 Verify Everything Works

✅ Login successful
✅ Dashboard loads
✅ No cookie errors
✅ All features work

---

## 🎉 You're Live!

Your SaaS is now running on a professional custom domain!

**Your URLs:**
- Frontend: `https://app.yourdomain.com`
- Backend API: `https://api.yourdomain.com`
- Database: Railway PostgreSQL (internal)

---

## 📊 DNS Configuration Summary

Here's what your DNS should look like:

| Type | Name | Value | Purpose |
|------|------|-------|---------|
| CNAME | app | cname.vercel-dns.com | Frontend (Vercel) |
| CNAME | api | xxx.up.railway.app | Backend (Railway) |
| A | @ | 76.76.21.21 | Root domain (optional) |

---

## 🔧 Troubleshooting

### Domain not working after 30 minutes?

**Check DNS propagation:**
```bash
nslookup app.yourdomain.com
nslookup api.yourdomain.com
```

Or use: https://dnschecker.org

### Still getting cookie errors?

1. Make sure both domains use HTTPS (not HTTP)
2. Verify CORS_ORIGINS includes your frontend domain
3. Clear browser cookies and cache
4. Try incognito/private browsing mode

### SSL certificate not working?

- Wait 5-10 minutes for automatic provisioning
- Check Railway/Vercel dashboard for SSL status
- Ensure DNS records are correct

---

## 💰 Cost Breakdown

| Service | Cost | What You Get |
|---------|------|--------------|
| Domain | $10-15/year | Your custom domain |
| Vercel | FREE | Frontend hosting, CDN, SSL |
| Railway | $5-10/month | Backend + Database |
| **Total** | **~$70-135/year** | Full SaaS platform |

---

## 🚀 Next Steps

1. **Set up email** for password resets (SendGrid, Mailgun)
2. **Add analytics** (Google Analytics, PostHog)
3. **Set up monitoring** (Sentry for errors)
4. **Configure backups** for database
5. **Add payment processing** (Stripe)

---

## 📞 Need Help?

**Common Issues:**
- DNS not propagating → Wait 24 hours
- SSL errors → Check HTTPS is enabled
- Cookie errors → Verify both domains use same root
- CORS errors → Check CORS_ORIGINS variable

**Resources:**
- Vercel Docs: https://vercel.com/docs
- Railway Docs: https://docs.railway.app
- DNS Checker: https://dnschecker.org

---

**Congratulations! Your SaaS is now live on a professional domain! 🎉**
