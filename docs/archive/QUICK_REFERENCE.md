# 🚀 Quick Reference Card

## URLs

| Service | URL |
|---------|-----|
| Frontend | https://heartfelt-benevolence-production-ba39.up.railway.app |
| Backend | https://coredentist-production.up.railway.app |
| Health | https://coredentist-production.up.railway.app/health |

## Login

```
Email:    admin@coredent.com
Password: Admin123!
```

## Database

```
Host:     caboose.proxy.rlwy.net:44462
Database: railway
User:     postgres
Password: FZHYAmmFYRIFaiZSwiDFJsZLHPtSIWnx
```

## Railway Project

- **Project**: practical-dream
- **Region**: us-east-4
- **Services**: PostgreSQL, Backend (coredentist), Frontend

## Key Files

| File | Purpose |
|------|---------|
| `coredent-api/Dockerfile` | Backend container |
| `coredent-style-main/Dockerfile` | Frontend container |
| `coredent-api/app/main.py` | Backend entry point |
| `coredent-style-main/nginx.conf` | Frontend routing |
| `create_test_user_simple.py` | Create test users |

## Testing Checklist

- [ ] Frontend loads
- [ ] Backend health check passes
- [ ] Login works
- [ ] Dashboard displays
- [ ] No console errors
- [ ] No CORS errors

## Common Commands

```bash
# Check backend health
curl https://coredentist-production.up.railway.app/health

# Connect to database
psql postgresql://postgres:FZHYAmmFYRIFaiZSwiDFJsZLHPtSIWnx@caboose.proxy.rlwy.net:44462/railway

# Create test user
python create_test_user_simple.py

# Check enum values
python check_enum.py
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Frontend won't load | Check Railway service status |
| Login fails | Verify credentials, check backend health |
| CORS errors | Verify FRONTEND_URL in backend env |
| Database errors | Check DATABASE_URL, verify credentials |

## Important Notes

⚠️ Change admin password after first login  
⚠️ Don't share credentials in production  
⚠️ Enable 2FA when available  
⚠️ Configure automated backups  
⚠️ Set up email notifications  

## Status

✅ Backend: Running  
✅ Frontend: Running  
✅ Database: Connected  
✅ Test User: Created  
✅ CORS: Configured  

**Ready for testing!**

