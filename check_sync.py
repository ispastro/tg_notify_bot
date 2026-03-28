"""Quick verification of database and model sync."""
import subprocess

print("=" * 60)
print("DATABASE & MODEL SYNCHRONIZATION CHECK")
print("=" * 60)

# Check User model
print("\n1. User Model Columns:")
from db.models import User
columns = [c.name for c in User.__table__.columns]
for col in columns:
    print(f"   - {col}")

required = ['full_name', 'gender']
print(f"\n2. Required Columns Check:")
for col in required:
    status = "[OK]" if col in columns else "[MISSING]"
    print(f"   {status} {col}")

# Check migration
print(f"\n3. Migration Status:")
result = subprocess.run(['alembic', 'current'], capture_output=True, text=True)
if '1d4fa529ddea' in result.stdout:
    print(f"   [OK] Migration 1d4fa529ddea applied (add_user_profile_fields)")
else:
    print(f"   [FAIL] Migration not applied")

# Check schema sync
print(f"\n4. Schema Sync Check:")
result = subprocess.run(['alembic', 'check'], capture_output=True, text=True)
if 'No new upgrade operations detected' in result.stdout:
    print(f"   [OK] Database schema matches models")
else:
    print(f"   [FAIL] Schema out of sync")

print("\n" + "=" * 60)
print("REGISTRATION FLOW: /start -> full_name -> gender -> batch")
print("=" * 60)
