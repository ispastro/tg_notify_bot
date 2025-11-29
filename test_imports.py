import sys
sys.path.insert(0, '.')

try:
    import handlers.users
    print("✓ handlers.users imported successfully")
    print(f"✓ Found {len([x for x in dir(handlers.users) if x.startswith('cmd_')])} command handlers")
except Exception as e:
    print(f"✗ Failed to import handlers.users: {e}")
    import traceback
    traceback.print_exc()

try:
    import handlers.admin  
    print("✓ handlers.admin imported successfully")
except Exception as e:
    print(f"✗ Failed to import handlers.admin: {e}")
