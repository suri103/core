import sqlite3
import json

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Set default values for the practice
default_working_hours = {
    "monday": {"start": "09:00", "end": "17:00", "enabled": True},
    "tuesday": {"start": "09:00", "end": "17:00", "enabled": True},
    "wednesday": {"start": "09:00", "end": "17:00", "enabled": True},
    "thursday": {"start": "09:00", "end": "17:00", "enabled": True},
    "friday": {"start": "09:00", "end": "17:00", "enabled": True},
    "saturday": {"start": "09:00", "end": "13:00", "enabled": False},
    "sunday": {"start": "09:00", "end": "13:00", "enabled": False},
}

# Store appointment types and chairs in settings JSON since columns don't exist
default_settings = {
    "appointment_types": [
        {"name": "Checkup", "duration": 30, "color": "#3B82F6"},
        {"name": "Cleaning", "duration": 45, "color": "#10B981"},
        {"name": "Filling", "duration": 60, "color": "#F59E0B"},
        {"name": "Root Canal", "duration": 90, "color": "#EF4444"},
        {"name": "Extraction", "duration": 45, "color": "#8B5CF6"},
    ],
    "chairs": [
        {"id": "1", "name": "Chair 1", "enabled": True},
        {"id": "2", "name": "Chair 2", "enabled": True},
    ]
}

cursor.execute('''
    UPDATE practices 
    SET working_hours = ?,
        settings = ?,
        website = COALESCE(website, ''),
        tax_rate = COALESCE(tax_rate, '0.0'),
        invoice_prefix = COALESCE(invoice_prefix, 'INV'),
        payment_terms = COALESCE(payment_terms, '30'),
        late_fee_percentage = COALESCE(late_fee_percentage, '0.0'),
        accepted_payment_methods = COALESCE(accepted_payment_methods, '["cash", "card", "check"]'),
        auto_send_invoices = COALESCE(auto_send_invoices, 0),
        auto_send_reminders = COALESCE(auto_send_reminders, 0),
        reminder_days_before = COALESCE(reminder_days_before, '3')
''', (
    json.dumps(default_working_hours),
    json.dumps(default_settings)
))

conn.commit()
print(f'Updated {cursor.rowcount} practice(s) with default settings')

# Verify the update
cursor.execute("SELECT name, working_hours, settings FROM practices")
practice = cursor.fetchone()
if practice:
    print(f"\nPractice: {practice[0]}")
    print(f"Working hours: {practice[1][:50]}...")
    print(f"Settings: {practice[2][:50]}...")

conn.close()
