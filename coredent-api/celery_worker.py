"""
Celery Worker Entry Point for CoreDent API
Executes asynchronous background tasks:
- Appointment & payment reminders
- Twilio SMS / SendGrid emails
- Insurance ERA (835) claims processing
- State sweeps (e.g. overdue invoice transitions)

Usage:
celery -A celery_worker.celery_app worker --loglevel=info -Q default,communications,reminders,emails
celery -A celery_worker.celery_app beat --loglevel=info
"""

from app.core.celery_app import celery_app

__all__ = ["celery_app"]

