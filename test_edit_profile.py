"""Test script for /edit_profile functionality"""
import sys
import asyncio

print("=" * 60)
print("EDIT PROFILE FUNCTIONALITY TEST")
print("=" * 60)

# Test 1: Check FSM States
print("\n1. Checking FSM States...")
try:
    from handlers.users import EditProfileStates
    states = [s for s in dir(EditProfileStates) if not s.startswith('_')]
    print(f"   [OK] EditProfileStates: {states}")
    
    required_states = ['choosing_field', 'entering_new_name', 'choosing_new_gender']
    for state in required_states:
        if state not in states:
            print(f"   [FAIL] Missing state: {state}")
            sys.exit(1)
    print(f"   [OK] All required states present")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Test 2: Check Command Handler
print("\n2. Checking /edit_profile command handler...")
try:
    from handlers.users import cmd_edit_profile
    print(f"   [OK] cmd_edit_profile function exists")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Test 3: Check Callback Handlers
print("\n3. Checking callback handlers...")
try:
    from handlers.users import handle_edit_name, handle_edit_gender, handle_edit_cancel
    print(f"   [OK] handle_edit_name exists")
    print(f"   [OK] handle_edit_gender exists")
    print(f"   [OK] handle_edit_cancel exists")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Test 4: Check State Processors
print("\n4. Checking state processors...")
try:
    from handlers.users import process_new_name, process_new_gender
    print(f"   [OK] process_new_name exists")
    print(f"   [OK] process_new_gender exists")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Test 5: Check Commands in Menu
print("\n5. Checking command menus...")
try:
    from utils.set_bot_commands import set_default_commands, set_admin_commands
    print(f"   [OK] Command menu functions exist")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

# Test 6: Check Database Model
print("\n6. Checking User model fields...")
try:
    from db.models import User
    columns = [c.name for c in User.__table__.columns]
    required = ['full_name', 'gender']
    for col in required:
        if col in columns:
            print(f"   [OK] {col} column exists")
        else:
            print(f"   [FAIL] {col} column missing")
            sys.exit(1)
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] ALL TESTS PASSED")
print("=" * 60)
print("\nManual Testing Steps:")
print("1. Send /edit_profile to the bot")
print("2. Verify inline keyboard appears with 3 buttons:")
print("   - 📛 Edit Name")
print("   - ⚧ Edit Gender")
print("   - ❌ Cancel")
print("3. Click 'Edit Name' and enter a new name")
print("4. Verify name updates successfully")
print("5. Send /edit_profile again")
print("6. Click 'Edit Gender' and select from keyboard")
print("7. Verify gender updates successfully")
print("8. Send /whoami to confirm changes")
print("=" * 60)
