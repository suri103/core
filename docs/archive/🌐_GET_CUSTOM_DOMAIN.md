# 🌐 How to Get a Custom .com Domain for Your SaaS

## What You Want
Instead of: `https://respectful-strength-production-ef28.up.railway.app`
You want: `https://app.coredent.com` (or your own domain)

---

## 🎯 Two-Step Process

### Step 1: Buy a Domain (15 minutes, ~$12/year)
### Step 2: Connect it to Your App (10 minutes, FREE)

---

## Step 1: Buy Your Domain

### Option A: Namecheap (Easiest - Recommended)

1. Go to: https://www.namecheap.com
2. Search for your domain name:
   - `coredent.com`
   - `coredentpms.com`
   - `mycoredent.com`
   - `getcoredent.com`
   - Or any name you want!
3. Add to cart (~$12/year)
4. Create account and checkout
5. Done! You own the domain

### Option B: GoDaddy

1. Go to: https://www.godaddy.com
2. Search for domain
3. Buy it (~$15/year)

### Option C: Cloudflare (Best for advanced users)

1. Go to: https://www.cloudflare.com/products/registrar/
2. Register domain (~$10/year)
3. Bonus: Free CDN and security

---

## Step 2: Deploy Frontend to Vercel (FREE)

**Why Vercel?**
- FREE hosting for frontend
- Easy custom domain setup
- Faster than Railway for static sites
- Professional SaaS companies use it

### 2.1 Create Vercel Account

1. Go to: https://vercel.com
2. Click "Sign Up"
3. Sign up with GitHub (recommended)

### 2.2 Deploy Your Frontend

**Option A: Connect GitHub (Easiest)**

1. Click "Add New Project"
2. Click "Import Git Repository"
3. Select your GitHub repo
4. Set **Root Directory**: `coredent-style-main`
5. Vercel auto-detects it's a Vite app
6. Add environment variable:
   ```
   VITE_API_BASE_URL=https://coredentist-production.up.railway.app/api/v1
   ```
7. Click "Deploy"
8. Wait 2-3 minutes
9. You get a URL like: `your-project.vercel.app`

**Option B: Deploy from Command Line**

```bash
# Install Vercel CLI
npm i -g vercel

# Go to frontend folder
cd coredent-style-main

# Deploy
vercel

# Follow prompts
```

### 2.3 Add Your Custom Domain to Vercel

1. In Vercel dashboard, click your project
2. Go to "Settings" → "Domains"
3. Click "Add Domain"
4. Enter: `app.coredent.com` (or `app.yourdomain.com`)
5. Vercel will show you DNS records to add

### 2.4 Configure DNS Records

Go to your domain registrar (Namecheap/GoDaddy/etc):

1. Find "DNS Settings" or "Manage DNS"
2. Add a CNAME record:
   ```
   Type: CNAME
   Name: app
   Value: cname.vercel-dns.com
   TTL: Auto (or 3600)
   ```
3. Save

**Wait 5-30 minutes for DNS to propagate**

### 2.5 Add Custom Domain to Railway Backend

1. Go to Railway dashboard
2. Click your backend service
3. Go to "Settings" → "Domains"
4. Click "Custom Domain"
5. Enter: `api.coredent.com` (or `api.yourdomain.com`)
6. Railway shows you a CNAME record

Go back to your domain DNS settings:

7. Add another CNAME record:
   ```
   Type: CNAME
   Name: api
   Value: [Railway provides this, like: xxx.up.railway.app]
   TTL: Auto
   ```
8. Save

**Wait 5-10 minutes**

### 2.6 Update Backend CORS

In Railway backend variables:

```
CORS_ORIGINS=https://app.coredent.com,https://coredent.com
```

### 2.7 Update Frontend API URL

In Vercel project settings → Environment Variables:

```
VITE_API_BASE_URL=https://api.coredent.com/api/v1
```

Redeploy frontend in Vercel.

---

## 🎉 Final Result

Your SaaS is now live at:
- **Frontend**: `https://app.coredent.com`
- **Backend API**: `https://api.coredent.com`
- **Database**: Railway PostgreSQL (internal)

Looks professional! ✨

---

## 💰 Total Cost

| Item | Cost | Frequency |
|------|------|-----------|
| Domain (.com) | $10-15 | Per year |
| Vercel (Frontend) | FREE | Forever |
| Railway (Backend + DB) | $5-10 | Per month |
| **Total** | **~$70-135** | **Per year** |

---

## 📊 DNS Configuration Summary

After setup, your DNS should look like:

| Type | Name | Value | Points To |
|------|------|-------|-----------|
| CNAME | app | cname.vercel-dns.com | Frontend (Vercel) |
| CNAME | api | xxx.up.railway.app | Backend (Railway) |
| A | @ | 76.76.21.21 | Root domain (optional) |

---

## ⚡ Quick Start (If You Already Have a Domain)

Already bought a domain? Here's the fast track:

1. **Deploy to Vercel**: https://vercel.com → Import GitHub repo
2. **Add domain in Vercel**: Settings → Domains → Add `app.yourdomain.com`
3. **Add CNAME in DNS**: `app` → `cname.vercel-dns.com`
4. **Add domain in Railway**: Settings → Domains → Add `api.yourdomain.com`
5. **Add CNAME in DNS**: `api` → `[railway-url].up.railway.app`
6. **Update CORS**: Backend variable `CORS_ORIGINS=https://app.yourdomain.com`
7. **Update API URL**: Vercel variable `VITE_API_BASE_URL=https://api.yourdomain.com/api/v1`
8. **Wait 10-30 minutes** for DNS propagation
9. **Open**: `https://app.yourdomain.com`
10. **Login**: admin@coredent.com / Admin123!

Done! 🚀

---

## 🔍 Check DNS Propagation

Use this tool to check if DNS is working:
https://dnschecker.org

Enter your domain and check if it points to the right place.

---

## 🎯 Why This Setup is Professional

**Benefits:**
- ✅ Custom branded domain (looks professional)
- ✅ HTTPS/SSL automatic (secure)
- ✅ Fast global CDN (Vercel)
- ✅ Cookies work perfectly (same root domain)
- ✅ Scalable (handles thousands of users)
- ✅ Affordable (~$10/month total)

**Used by real SaaS companies:**
- Notion uses Vercel
- Linear uses Vercel
- Many Y Combinator startups use this stack

---

## 📝 Domain Name Ideas

If `coredent.com` is taken, try:

- `coredentpms.com` (PMS = Practice Management System)
- `mycoredent.com`
- `getcoredent.com`
- `coredentapp.com`
- `coredent.io` (tech companies love .io)
- `coredent.app` (modern SaaS domain)
- `usecoredent.com`

---

## 🚨 Important Notes

1. **First fix the current deployment** (add ENCRYPTION_KEY to Railway)
2. **Then** set up custom domain
3. Don't skip step 1 - your app needs to work first!

---

## Need Help?

**Detailed guide**: Read `🚀_CUSTOM_DOMAIN_SETUP_GUIDE.md`

**Quick questions:**
- "How long does DNS take?" → 5-30 minutes usually
- "Do I need to buy hosting?" → No! Vercel is FREE
- "Can I use my existing domain?" → Yes! Just add DNS records
- "What if domain is taken?" → Try variations or different TLD (.io, .app)

---

**Start by buying a domain at Namecheap.com - takes 5 minutes!**
