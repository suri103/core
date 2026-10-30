# CoreDent API - Quick Start Guide

Get the backend running in 5 minutes!

## Option 1: Docker (Recommended - Fastest)

### Prerequisites
- Docker Desktop installed
- Docker Compose installed

### Steps

```bash
# 1. Navigate to API directory
cd coredent-api

# 2. Create environment file
cp .env.example .env

# 3. Start all services (PostgreSQL + Redis + API)
docker-compose up -d

# 4. Wait for services to be healthy (30 seconds)
docker-compose ps

# 5. Run database migrations
docker-compose exec api alembic upgrade head

# 6. Create initial admin user
docker-compose exec api python scripts/create_admin.py

# 7. API is now running!
# - API: http://localhost:3000
# - Docs: http://localhost:3000/docs
# - Health: http://localhost:3000/health
```

### Test the API

```bash
# Health check
curl http://localhost:3000/health

# Login (use credentials from create_admin.py)
curl -X POST http://localhost:3000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@coredent.com","password":"Admin123!"}'
```

### View Logs

```bash
# All services
docker-compose logs -f

# Just API
docker-compose logs -f api

# Just database
docker-compose logs -f postgres
```

### Stop Services

```bash
# Stop but keep data
docker-compose stop

# Stop and remove containers (keeps data)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

---

## Option 2: Local Development (Python)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ installed and running
- Redis installed (optional)

### Steps

```bash
# 1. Navigate to API directory
cd coredent-api

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create PostgreSQL database
createdb coredent_db

# 6. Create environment file
cp .env.example .env

# 7. Edit .env with your database credentials
# DATABASE_URL=postgresql://your_user:your_password@localhost:5432/coredent_db

# 8. Run database migrations
alembic upgrade head

# 9. Create initial admin user
python scripts/create_admin.py

# 10. Start the API
uvicorn app.main:app --reload --port 3000
```

### API is now running at:
- http://localhost:3000
- Docs: http://localhost:3000/docs

---

## Option 3: Windows Quick Setup

### Using PowerShell

```powershell
# 1. Install Python 3.11+ from python.org

# 2. Install PostgreSQL from postgresql.org

# 3. Clone and setup
cd coredent-api
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Create database
# Open pgAdmin or use psql:
# CREATE DATABASE coredent_db;

# 5. Configure .env
copy .env.example .env
# Edit .env with your settings

# 6. Run migrations
alembic upgrade head

# 7. Create admin
python scripts\create_admin.py

# 8. Start API
uvicorn app.main:app --reload --port 3000
```

---

## Connecting Frontend to Backend

### Update Frontend Environment

Edit `coredent-style-main/.env`:

```env
VITE_API_BASE_URL=http://localhost:3000/api/v1
VITE_ENABLE_DEMO_MODE=false
```

### Restart Frontend

```bash
cd coredent-style-main
npm run dev
```

### Test Full Stack

1. Open frontend: http://localhost:8080
2. Login with admin credentials
3. Backend API calls will now work!

---

## Default Admin Credentials

After running `create_admin.py`:

```
Email: admin@coredent.com
Password: Admin123!
```

**⚠️ Change these immediately in production!**

---

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 3000
# Windows:
netstat -ano | findstr :3000

# Mac/Linux:
lsof -i :3000

# Kill the process or use different port:
uvicorn app.main:app --reload --port 3001
```

### Database Connection Error

```bash
# Check PostgreSQL is running
# Windows:
services.msc  # Look for PostgreSQL

# Mac/Linux:
pg_isready

# Check connection string in .env
DATABASE_URL=postgresql://user:password@localhost:5432/coredent_db
```

### Import Errors

```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Check Python version
python --version  # Should be 3.11+
```

### Docker Issues

```bash
# Restart Docker Desktop

# Remove all containers and start fresh
docker-compose down -v
docker-compose up -d --build

# Check container logs
docker-compose logs api
```

---

## Next Steps

1. ✅ API is running
2. ✅ Database is set up
3. ✅ Admin user created
4. 📝 Read API documentation at /docs
5. 🔗 Connect frontend
6. 🧪 Run tests: `pytest`
7. 📊 Check health: http://localhost:3000/health

---

## Development Workflow

```bash
# Make code changes
# API auto-reloads with --reload flag

# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Run tests
pytest

# Check code quality
black app/
flake8 app/
mypy app/
```

---

## Production Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for production setup.

---

## Support

- 📧 Email: support@coredent.com
- 📚 Docs: http://localhost:3000/docs
- 🐛 Issues: Report bugs in GitHub

---

**🎉 You're all set! The backend is running and ready to connect with the frontend.**
