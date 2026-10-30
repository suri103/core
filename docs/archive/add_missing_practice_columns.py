import sqlite3
import json

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

print("Adding missing columns to practices table...")

# Add appointment_types column
try:
    cursor.execute("ALTER TABLE practices ADD COLUMN appointment_types JSON DEFAULT '[]'")
    print("✓ Added appointment_types column")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("✓ appointment_types column already exists")
    else:
        print(f"✗ Error adding appointment_types: {e}")

# Add chairs column
try:
    cursor.execute("ALTER TABLE practices ADD COLUMN chairs JSON DEFAULT '[]'")
    print("✓ Added chairs column")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("✓ chairs column already exists")
    else:
        print(f"✗ Error adding chairs: {e}")

conn.commit()

# Now populate with default values
default_appointment_types = [
    {"name": "Checkup", "duration": 30, "color": "#3B82F6"},
    {"name": "Cleaning", "duration": 45, "color": "#10B981"},
    {"name": "Filling", "duration": 60, "color": "#F59E0B"},
    {"name": "Root Canal", "duration": 90, "color": "#EF4444"},
    {"name": "Extraction", "duration": 45, "color": "#8B5CF6"},
]

default_chairs = [
    {"id": "1", "name": "Chair 1", "enabled": True},
    {"id": "2", "name": "Chair 2", "enabled": True},
]

default_working_hours = {
    "monday": {"start": "09:00", "end": "17:00", "enabled": True},
    "tuesday": {"start": "09:00", "end": "17:00", "enabled": True},
    "wednesday": {"start": "09:00", "end": "17:00", "enabled": True},
    "thursday": {"start": "09:00", "end": "17:00", "enabled": True},
    "friday": {"start": "09:00", "end": "17:00", "enabled": True},
    "saturday": {"start": "09:00", "end": "13:00", "enabled": False},
    "sunday": {"start": "09:00", "end": "13:00", "enabled": False},
}

print("\nPopulating default values...")

cursor.execute('''
    UPDATE practices 
    SET appointment_types = ?,
        chairs = ?,
        working_hours = ?,
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
    json.dumps(default_appointment_types),
    json.dumps(default_chairs),
    json.dumps(default_working_hours)
))

conn.commit()
print(f'✓ Updated {cursor.rowcount} practice(s) with default settings')

# Verify the update
cursor.execute("SELECT name, appointment_types, chairs, working_hours FROM practices")
practice = cursor.fetchone()
if practice:
    print(f"\n✓ Practice: {practice[0]}")
    print(f"  - Appointment types: {len(json.loads(practice[1]))} types configured")
    print(f"  - Chairs: {len(json.loads(practice[2]))} chairs configured")
    print(f"  - Working hours: {len(json.loads(practice[3]))} days configured")

conn.close()
print("\n✓ Database migration complete!")
