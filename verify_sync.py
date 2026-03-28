"""Verification script to check code synchronization."""
import sys
import os

# Set UTF-8 encoding for Windows console
os.system('chcp 65001 >nul 2>&1')

print("=" * 60)
print("CODE SYNCHRONIZATION VERIFICATION")
print("=" * 60)

# Check User model structure
print("\n1. Checking User model...")
try:
    from db.models import User
    columns = [c.name for c in User.__table__.columns]
    print(f"   [OK] User columns: {columns}")
    
    required = ['full_name', 'gender']
    missing = [col for col in required if col not in columns]
    if missing:
        print(f"   [FAIL] Missing columns: {missing}")
        sys.exit(1)
    else:
        print(f"   [OK] All required columns present: {required}")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Check FSM states
print("\n2. Checking FSM states...")
try:
    from handlers.users import RegisterStates
    states = [s for s in dir(RegisterStates) if not s.startswith('_')]
    print(f"   [OK] RegisterStates: {states}")
    
    required_states = ['entering_full_name', 'choosing_gender', 'choosing_batch']
    for state in required_states:
        if state not in states:
            print(f"   [FAIL] Missing state: {state}")
            sys.exit(1)
    print(f"   [OK] All required states present")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Check handlers
print("\n3. Checking handlers...")
try:
    from handlers.users import GENDERS, BATCHES
    print(f"   [OK] GENDERS: {GENDERS}")
    print(f"   [OK] BATCHES: {BATCHES}")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Check migration status
print("\n4. Checking migration status...")
import subprocess
result = subprocess.run(
    ['alembic', 'current'],
    capture_output=True,
    text=True
)
if '1d4fa529ddea' in result.stdout:
    print(f"   [OK] Migration applied: 1d4fa529ddea (add_user_profile_fields)")
else:
    print(f"   [FAIL] Migration not applied")
    sys.exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] ALL CHECKS PASSED - CODE IS SYNCHRONIZED")
print("=" * 60)
