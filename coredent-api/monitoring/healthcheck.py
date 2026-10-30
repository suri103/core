#!/usr/bin/env python3
"""
Health Check Script for CoreDent API
Run this periodically to verify system health
"""

import sys
import requests
import psycopg2
from datetime import datetime, timezone
import os

# Configuration
API_URL = os.getenv("API_URL")
if not API_URL:
    raise ValueError("API_URL environment variable is required for healthcheck")
DB_URL = os.getenv("DATABASE_URL", "")
ALERT_WEBHOOK = os.getenv("ALERT_WEBHOOK_URL", "")

def check_api_health():
    """Check if API is responding"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API health check passed")
            return True
        else:
            print(f"❌ API health check failed: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False

def check_database():
    """Check database connectivity"""
    if not DB_URL:
        print("⚠️  Database check skipped (no DB_URL)")
        return True
    
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        print("✅ Database check passed")
        return True
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def check_disk_space():
    """Check available disk space"""
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_percent = (free / total) * 100
        
        if free_percent < 10:
            print(f"❌ Low disk space: {free_percent:.1f}% free")
            return False
        elif free_percent < 20:
            print(f"⚠️  Disk space warning: {free_percent:.1f}% free")
            return True
        else:
            print(f"✅ Disk space OK: {free_percent:.1f}% free")
            return True
    except Exception as e:
        print(f"⚠️  Disk space check failed: {e}")
        return True

def send_alert(message):
    """Send alert to webhook"""
    if not ALERT_WEBHOOK:
        return
    
    try:
        payload = {
            "text": f"🚨 CoreDent Alert: {message}",
            # Timezone FIX: aware UTC (utcnow is naive/deprecated).
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        requests.post(ALERT_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send alert: {e}")

def main():
    """Run all health checks"""
    print(f"\n{'='*50}")
    print(f"CoreDent Health Check - {datetime.now(timezone.utc)}")
    print(f"{'='*50}\n")
    
    checks = [
        ("API", check_api_health()),
        ("Database", check_database()),
        ("Disk Space", check_disk_space()),
    ]
    
    failed_checks = [name for name, result in checks if not result]
    
    print(f"\n{'='*50}")
    if failed_checks:
        print("❌ Health check FAILED")
        print(f"Failed checks: {', '.join(failed_checks)}")
        send_alert(f"Health check failed: {', '.join(failed_checks)}")
        sys.exit(1)
    else:
        print("✅ All health checks PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
