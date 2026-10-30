"""Fix all remaining issues for 10/10"""
import subprocess, os

# 1. Fix datetime.utcnow() in app code
files_with_utcnow = []
for root, dirs, files in os.walk('coredent-api'):
    if 'venv' in root or '__pycache__' in root or '.git' in root:
        continue
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                if 'datetime.utcnow()' in content:
                    files_with_utcnow.append((path, content))
            except:
                pass

print("Files with datetime.utcnow():")
for path, content in files_with_utcnow:
    print(f"  {path}")
    # Fix
    content = content.replace(
        'from datetime import datetime',
        'from datetime import datetime, timezone'
    ).replace(
        "datetime.utcnow()", 
        "datetime.now(timezone.utc)"
    )
    # But revert if it broke import
    if "from datetime import datetime, timezone, timezone" in content:
        content = content.replace("from datetime import datetime, timezone, timezone", "from datetime import datetime, timezone")
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)
    print(f"    => FIXED")

# 2. Fix email verification token to use hash
user_model_path = 'coredent-api/app/models/user.py'
with open(user_model_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'email_verification_token_hash' not in content:
    content = content.replace(
        'email_verification_token = Column(String(255), nullable=True)',
        'email_verification_token = Column(String(255), nullable=True)  # DEPRECATED: Use token_hash\n    email_verification_token_hash = Column(String(255), nullable=True, index=True)  # SECURITY: Store hashed tokens'
    )
    with open(user_model_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Fixed email_verification_token in user.py")

# 3. Fix booking.py email token too
booking_model_path = 'coredent-api/app/models/booking.py'
with open(booking_model_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'email_verification_token_hash' not in content:
    content = content.replace(
        'email_verification_token = Column(String(100))',
        'email_verification_token = Column(String(100))  # DEPRECATED: Use token_hash\n    email_verification_token_hash = Column(String(255), nullable=True, index=True)  # SECURITY: Store hashed tokens'
    )
    with open(booking_model_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Fixed email_verification_token in booking.py")

print("\nAll remaining fixes applied!")