# Infrastructure Autoscaling Guide

This document describes autoscaling strategies and configurations for CoreDent PMS production deployment.

## Table of Contents
1. [Overview](#overview)
2. [Backend Autoscaling](#backend-autoscaling)
3. [Database Scaling](#database-scaling)
4. [Redis/Cache Scaling](#rediscache-scaling)
5. [Frontend CDN](#frontend-cdn)
6. [Monitoring & Alerts](#monitoring--alerts)
7. [Cost Optimization](#cost-optimization)

---

## Overview

CoreDent PMS is designed for horizontal scaling with the following components:

| Component | Scaling Strategy | Complexity |
|-----------|-----------------|------------|
| FastAPI Backend | Horizontal (multiple instances) | Low |
| PostgreSQL | Vertical + Read Replicas | Medium |
| Redis | Vertical + Clustering | Medium |
| Frontend (Vercel) | Automatic CDN | None |
| File Storage | S3 (auto-scaling) | None |

### Target Metrics

| Metric | Warning | Critical |
|--------|---------|----------|
| CPU Usage | >70% | >90% |
| Memory Usage | >75% | >90% |
| Response Time P99 | >300ms | >500ms |
| Error Rate | >1% | >5% |
| DB Connections | >80% pool | >95% pool |

---

## Backend Autoscaling

### Railway (Recommended for startups)

Railway provides automatic vertical scaling. Configure via `railway.toml`:

```toml
[deployments]
num_instances = 3
max_instances = 10
min_instances = 1

[deployments.autoscaling]
enabled = true
metric = "cpu"  # or "memory"
threshold = 70
scale_up_cooldown_seconds = 120
scale_down_cooldown_seconds = 300
```

### Docker Compose (Self-hosted)

```yaml
services:
  api:
    image: coredent-api:latest
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    scaling:
      - replicas: 3
        when: "cpu_utilization > 70"
        cooldown: 120

  api-worker:
    image: coredent-api:latest
    command: celery -A app.core.celery_app worker
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### Kubernetes (Enterprise)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: coredent-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: coredent-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 120
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

---

## Database Scaling

### PostgreSQL Connection Pooling

Use PgBouncer for connection pooling:

```ini
[databases]
coredent = host=postgres port=5432 dbname=coredent

[pgbouncer]
listen_port = 6432
listen_addr = 0.0.0.0
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 500
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3
```

### Read Replicas

Route read queries to replicas:

```python
# app/core/database.py
import os

class DatabaseRouter:
    def db_for_read(self, model):
        if os.getenv("USE_READ_REPLICA", "false").lower() == "true":
            return "replica"
        return "default"

    def db_for_write(self, model):
        return "default"
```

### Railway Database Scaling

```toml
[database]
plan = "starter"  # or "basic", "standard", "pro"
```

---

## Redis/Cache Scaling

### Railway Redis

Redis on Railway is vertically scaled. For production:
- Starter: 256MB (dev/small)
- Basic: 1GB (production small)
- Standard: 4GB (production medium)
- Pro: 16GB (enterprise)

### Redis Sentinel (High Availability)

```python
# app/core/redis_config.py
import os

REDIS_SENTINEL_CONFIG = {
    "sentinel_kwargs": {
        "socket_timeout": 5,
        "sentinel_timeout": 5,
    },
    "sentinels": [
        ("redis-sentinel-1", 26379),
        ("redis-sentinel-2", 26379),
        ("redis-sentinel-3", 26379),
    ],
    "service_name": "coredent-master",
    "password": os.getenv("REDIS_PASSWORD"),
}
```

### Redis Cluster (Large Scale)

```python
from redis.cluster import RedisCluster

rc = RedisCluster(
    startup_nodes=[
        {"host": "redis-1", "port": 6379},
        {"host": "redis-2", "port": 6379},
        {"host": "redis-3", "port": 6379},
    ],
    password=os.getenv("REDIS_PASSWORD"),
    max_connections=100,
)
```

---

## Frontend CDN

Vercel automatically handles:
- Global CDN distribution
- Edge caching
- Automatic SSL
- DDoS protection

### Cache Headers

```nginx
# nginx.conf
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location /api/ {
    add_header Cache-Control "no-store";
}
```

### Vercel Config

```json
// vercel.json
{
  "routes": [
    { "src": "/api/(.*)", "dest": "https://coredent-api.up.railway.app/api/$1" },
    { "src": "/(.*)", "dest": "/index.html" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" }
      ]
    }
  ]
}
```

---

## Monitoring & Alerts

### Prometheus Metrics

CoreDent exposes Prometheus metrics at `/metrics`:

```python
# Key metrics to monitor
- coredent_http_requests_total{method, endpoint, status}
- coredent_http_request_duration_seconds{endpoint}
- coredent_db_connections_active
- coredent_redis_connections_active
- coredent_celery_tasks_total{status}
```

### Alertmanager Config

```yaml
# alertmanager.yml
route:
  group_by: ['alertname']
  receiver: 'slack'

receivers:
- name: 'slack'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/xxx'
    channel: '#alerts'
    send_resolved: true
```

### Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic liveness |
| `/health/ready` | Readiness (DB + Redis) |
| `/health/live` | Liveness |
| `/metrics` | Prometheus metrics |

---

## Cost Optimization

### Instance Sizing Guide

| Practice Size | API Instances | Memory | Redis |
|--------------|-------------|--------|-------|
| 1-10 users | 1 | 512MB | 256MB |
| 10-50 users | 2 | 1GB | 1GB |
| 50-200 users | 4 | 2GB | 2GB |
| 200-500 users | 8 | 4GB | 4GB |
| 500+ users | 16+ | 8GB | 8GB |

### Cost Saving Tips

1. **Use spot/preemptible instances** - 60-70% cheaper
2. **Scale down during off-hours** - Scheduled scaling
3. **Enable caching** - Reduce DB load
4. **Use connection pooling** - PgBouncer
5. **Compress responses** - nginx gzip
6. **Monitor and right-size** - Regular review

### Scheduled Scaling (Cost-Optimized)

```python
# Example: Scale down on nights/weekends
from celery import Celery
from celery.task import periodic_task
from datetime import time

@periodic_task(run_every=crontab(hour=20, minute=0))  # 8 PM
def scale_down_api():
    """Scale down to minimum instances during off-hours"""
    # Call Railway/Render API to reduce instances
    pass

@periodic_task(run_every=crontab(hour=7, minute=0))  # 7 AM
def scale_up_api():
    """Scale up to normal during business hours"""
    pass
```

---

## Quick Start Commands

### Run Load Test

```bash
cd scripts
python load_test.py
```

### Check Health

```bash
curl https://your-api.com/health
curl https://your-api.com/health/ready
```

### Monitor Logs

```bash
# Railway
railway logs --tail

# Docker
docker-compose logs -f api
```

---

## Support

For scaling issues or questions, review:
- [Load Testing Scripts](../scripts/load_test.py)
- [Deployment Guide](../DEPLOYMENT_GUIDE.md)
- [Monitoring Setup](../monitoring/)
