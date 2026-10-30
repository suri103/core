# ⚡ Quick Start Testing

## 🎯 Do This Now

### Step 1: Create Test User (2 minutes)
```bash
cd coredent-api
python scripts/create_admin.py
```

**Credentials Created:**
- Email: `admin@coredent.com`
- Password: `Admin123!`

### Step 2: Open Frontend (1 minute)
Go to: https://heartfelt-benevolence-production-ba39.up.railway.app

You should see login page.

### Step 3: Login (1 minute)
1. Enter email: `admin@coredent.com`
2. Enter password: `Admin123!`
3. Click Login

### Step 4: Check Dashboard (1 minute)
- Should see dashboard with data
- Should see patient count
- Should see appointments
- No red errors in console (F12)

### Step 5: Test Pages (5 minutes)
Click on:
- Patients
- Appointments
- Schedule
- Billing
- Insurance
- Reports

Each should load without errors.

---

## ✅ Success Indicators

✅ All working if:
- Frontend loads
- Can login
- Dashboard shows data
- Pages load without errors
- No CORS errors in console
- No red errors anywhere

---

## ❌ If Something Fails

### Frontend Won't Load
- Check URL: https://heartfelt-benevolence-production-ba39.up.railway.app
- Open DevTools (F12) → Console
- Look for red errors
- Try incognito window

### Login Fails
- Check email: `admin@coredent.com`
- Check password: `Admin123!`
- Open DevTools (F12) → Network tab
- Look for failed API calls
- Check for CORS errors

### CORS Error in Console
- Go to Railway dashboard
- Click backend service (coredentist)
- Click Variables
- Check CORS_ORIGINS is set to:
  ```
  https://heartfelt-benevolence-production-ba39.up.railway.app
  ```

### Data Doesn't Load
- Open DevTools (F12) → Network tab
- Look for failed API calls
- Check response status codes
- Look for 401/403/500 errors

---

## 📞 Need Help?

1. Check console for error messages
2. Check Network tab for failed requests
3. Check Railway logs
4. Review `🎯_COMPLETE_TESTING_GUIDE.md`

---

## 🎉 That's It!

Your application is live and ready to test!

**Frontend**: https://heartfelt-benevolence-production-ba39.up.railway.app
**Backend**: https://coredentist-production.up.railway.app
