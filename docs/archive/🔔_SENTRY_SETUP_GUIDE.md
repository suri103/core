# 🔔 SENTRY SETUP GUIDE

**Date**: April 13, 2026  
**Time Required**: 5-10 minutes  
**Status**: Ready to Setup

---

## 🎯 WHAT IS SENTRY?

Sentry is an error tracking and monitoring platform that will:
- ✅ Capture all errors and exceptions in real-time
- ✅ Alert you when critical issues occur
- ✅ Track security events (failed logins, suspicious activity)
- ✅ Monitor performance issues
- ✅ Provide detailed error context and stack traces

**Your code is already integrated with Sentry** - you just need to get the DSN (Data Source Name) and add it to Railway!

---

## 📋 STEP-BY-STEP SETUP

### Step 1: Create Sentry Account (2 minutes)

1. Go to **https://sentry.io**
2. Click **"Get Started"** or **"Sign Up"**
3. Choose **"Sign up with GitHub"** (easiest) or use email
4. Complete the signup process

---

### Step 2: Create Project (2 minutes)

1. After login, you'll see **"Create a Project"**
2. Select platform: **Python**
3. Set alert frequency: **"Alert me on every new issue"** (recommended for beta)
4. Project name: **`coredent-api`**
5. Click **"Create Project"**

---

### Step 3: Get Your DSN (1 minute)

After creating the project, you'll see a setup page with your DSN.

**Your DSN looks like this**:
```
https://1234567890abcdef@o123456.ingest.sentry.io/7654321
```

**Copy this DSN** - you'll need it in the next step!

**Can't find your DSN?**
1. Go to **Settings** (gear icon)
2. Click **Projects** → **coredent-api**
3. Click **Client Keys (DSN)**
4. Copy the **DSN** value

---

### Step 4: Add DSN to Railway (2 minutes)

#### Option A: Using Railway Dashboard (Recommended)

1. Go to **https://railway.app**
2. Select your **CoreDent project**
3. Click on your **backend service**
4. Go to **Variables** tab
5. Click **"+ New Variable"**
6. Add:
   ```
   Variable: SENTRY_DSN
   Value: <paste your DSN here>
   ```
7. Click **"Add"**

#### Option B: Using Railway CLI

```bash
# Set the DSN
railway variables set SENTRY_DSN="<your-dsn-here>"
```

---

### Step 5: Restart Backend (1 minute)

#### Option A: Using Railway Dashboard

1. In Railway dashboard
2. Click on your **backend service**
3. Go to **Settings** tab
4. Scroll down and click **"Restart"**

#### Option B: Using Railway CLI

```bash
railway restart
```

---

### Step 6: Test Sentry (2 minutes)

#### Test 1: Trigger a Test Error

```bash
# This will send a test error to Sentry
curl https://your-backend.railway.app/api/v1/test-error
```

**Expected**: You should see an error in your Sentry dashboard within 30 seconds!

#### Test 2: Check Sentry Dashboard

1. Go to **https://sentry.io**
2. Click on **coredent-api** project
3. You should see the test error appear in **Issues**

---

## ✅ VERIFICATION CHECKLIST

- [ ] Sentry account created
- [ ] Project "coredent-api" created
- [ ] DSN copied
- [ ] DSN added to Railway variables
- [ ] Backend restarted
- [ ] Test error sent
- [ ] Error appears in Sentry dashboard

---

## 🔔 WHAT SENTRY WILL MONITOR

### Errors & Exceptions:
- ✅ Python exceptions and crashes
- ✅ Database errors
- ✅ API endpoint failures
- ✅ Authentication errors

### Security Events:
- ✅ Failed login attempts
- ✅ Suspicious activity
- ✅ Rate limit violations
- ✅ File upload attacks

### Performance:
- ✅ Slow API endpoints
- ✅ Database query performance
- ✅ Memory usage issues

---

## 📊 SENTRY DASHBOARD OVERVIEW

### Issues Tab:
- See all errors and exceptions
- Click on any issue to see details
- View stack traces and context

### Performance Tab:
- See slow endpoints
- Identify bottlenecks
- Track response times

### Alerts Tab:
- Configure email/Slack alerts
- Set up custom alert rules
- Get notified of critical issues

---

## 🚨 RECOMMENDED ALERT SETTINGS

### For Beta Launch:

1. **Email Alerts**: ON
   - Alert on every new issue
   - Daily summary of all issues

2. **Slack Integration** (Optional):
   - Connect Slack workspace
   - Get real-time alerts in #alerts channel

3. **Alert Rules**:
   - Alert when error rate > 10/minute
   - Alert on any security-related errors
   - Alert on database connection failures

---

## 🔧 TROUBLESHOOTING

### DSN Not Working?

**Check 1**: Verify DSN format
```
✅ Correct: https://abc123@o123.ingest.sentry.io/456
❌ Wrong: abc123 (missing https://)
❌ Wrong: https://sentry.io/abc123 (wrong format)
```

**Check 2**: Verify environment variable
```bash
# Check if DSN is set in Railway
railway variables get SENTRY_DSN
```

**Check 3**: Check backend logs
```bash
# Look for Sentry initialization message
railway logs
# Should see: "Sentry initialized successfully"
```

### No Errors Appearing?

**Check 1**: Wait 30-60 seconds
- Sentry can take up to 1 minute to show new errors

**Check 2**: Verify backend restarted
- Make sure you restarted after adding DSN

**Check 3**: Check Sentry project
- Make sure you're looking at the correct project

---

## 💡 SENTRY BEST PRACTICES

### 1. Set Up Alerts
- Configure email alerts for critical errors
- Set up Slack integration for team notifications

### 2. Review Daily
- Check Sentry dashboard daily during beta
- Look for patterns in errors
- Fix high-frequency issues first

### 3. Use Releases
- Tag errors with release versions
- Track which version introduced bugs
- Monitor error rates after deployments

### 4. Add Context
- Sentry automatically captures:
  - User ID
  - Request URL
  - HTTP method
  - Headers
  - Stack trace

---

## 📞 SENTRY RESOURCES

- **Dashboard**: https://sentry.io
- **Documentation**: https://docs.sentry.io/platforms/python/
- **Support**: https://sentry.io/support/
- **Status**: https://status.sentry.io/

---

## 🎉 WHAT'S NEXT?

Once Sentry is set up:

1. ✅ **Migrations**: COMPLETE
2. ✅ **Sentry**: COMPLETE
3. ⏳ **Test Login**: 5 minutes
4. 🚀 **LAUNCH BETA!**

---

## 📋 QUICK REFERENCE

### Your Sentry DSN:
```
SENTRY_DSN=<paste your DSN here>
```

### Railway Command:
```bash
railway variables set SENTRY_DSN="<your-dsn>"
railway restart
```

### Test Command:
```bash
curl https://your-backend.railway.app/health
```

---

**Status**: ⏳ Awaiting Sentry DSN  
**Time Required**: 5-10 minutes  
**Next Action**: Go to https://sentry.io and create account

---

# 🚀 LET'S SET UP SENTRY!

**Step 1**: Go to https://sentry.io  
**Step 2**: Create account  
**Step 3**: Create project "coredent-api"  
**Step 4**: Copy DSN  
**Step 5**: Add to Railway  
**Step 6**: Restart backend  
**Step 7**: 🎉 Done!

