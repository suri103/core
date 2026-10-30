#!/usr/bin/env python3
"""
Performance Monitoring Script for CoreDent API
Checks response times and alerts if too slow
"""

import sys
import requests
import time
from datetime import datetime, timezone
import os

# Configuration
API_URL = os.getenv("API_URL")
if not API_URL:
    raise ValueError("API_URL environment variable is required for monitoring")
ALERT_WEBHOOK = os.getenv("ALERT_WEBHOOK_URL", "")
MAX_RESPONSE_TIME = float(os.getenv("MAX_RESPONSE_TIME", "2.0"))  # seconds

def check_endpoint_performance(endpoint, max_time=MAX_RESPONSE_TIME):
    """Check response time of an endpoint"""
    url = f"{API_URL}{endpoint}"
    
    try:
        start = time.time()
        response = requests.get(url, timeout=10)
        duration = time.time() - start
        
        status = "✅" if duration < max_time else "⚠️"
        print(f"{status} {endpoint}: {duration:.3f}s (max: {max_time}s)")
        
        return {
            "endpoint": endpoint,
            "duration": duration,
            "status_code": response.status_code,
            "success": duration < max_time and response.status_code == 200
        }
    except Exception as e:
        print(f"❌ {endpoint}: Failed - {e}")
        return {
            "endpoint": endpoint,
            "duration": None,
            "status_code": None,
            "success": False,
            "error": str(e)
        }

def send_alert(message):
    """Send alert to webhook"""
    if not ALERT_WEBHOOK:
        return
    
    try:
        payload = {
            "text": f"⚠️ CoreDent Performance Alert: {message}",
            # Timezone FIX: aware UTC (utcnow is naive/deprecated).
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        requests.post(ALERT_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send alert: {e}")

def main():
    """Run performance checks"""
    print(f"\n{'='*50}")
    print(f"CoreDent Performance Check - {datetime.now(timezone.utc)}")
    print(f"{'='*50}\n")
    
    # Endpoints to check
    endpoints = [
        "/health",
        "/api/v1/patients",
        "/api/v1/appointments",
    ]
    
    results = [check_endpoint_performance(ep) for ep in endpoints]
    
    # Analyze results
    failed = [r for r in results if not r["success"]]
    slow = [r for r in results if r["duration"] and r["duration"] > MAX_RESPONSE_TIME]
    
    print(f"\n{'='*50}")
    if failed:
        print("❌ Performance check FAILED")
        print(f"Failed endpoints: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"  - {r['endpoint']}: {r.get('error', 'Slow response')}")
        send_alert(f"{len(failed)} endpoints failed performance check")
        sys.exit(1)
    elif slow:
        print("⚠️  Some endpoints are slow")
        for r in slow:
            print(f"  - {r['endpoint']}: {r['duration']:.3f}s")
        send_alert(f"{len(slow)} endpoints are slow")
        sys.exit(0)
    else:
        print("✅ All endpoints performing well")
        sys.exit(0)

if __name__ == "__main__":
    main()
