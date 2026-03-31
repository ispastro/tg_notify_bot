"""Test personalization feature locally."""
import asyncio
import sys
import io
from utils.message_utils import personalize_message

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_personalize_message():
    """Test the personalize_message function."""
    
    # Test 1: English message
    message1 = "Hello {name}, welcome to the meeting!"
    result1 = personalize_message(message1, "Haile A")
    print(f"Test 1 (English):")
    print(f"  Input:  {message1}")
    print(f"  Output: {result1}")
    print(f"  ✅ PASS" if result1 == "Hello Haile A, welcome to the meeting!" else "  ❌ FAIL")
    print()
    
    # Test 2: Amharic message
    message2 = "ሰላም {name}\nዛሬ ጸሎት፣ መዝሙር ጨዋታ ና ሌሎችንም መርሃ ግብራትን\nያካተተ ልዩ የቤተሰብ👨👩👧👧 ጉባኤ አለ::\n📍 የት? ማኅበረ ቅዱሳን ሕንጻ 3ኛ ፎቅ\n🕐 መቼ? ዛሬ 11፡30\n\n📢 ማሳሰቢያ፡ እናም {name} ቤተሰብ ከሌለህ form ሞልተህ ስለሚመደብልህ መቅረት በፍጹም አይፈቀድም! 😊"
    result2 = personalize_message(message2, "Abebe Kebede")
    print(f"Test 2 (Amharic with multiple {{name}}):")
    print(f"  Input has {{name}}: {'{name}' in message2}")
    print(f"  Output has {{name}}: {'{name}' in result2}")
    print(f"  Output has 'Abebe Kebede': {'Abebe Kebede' in result2}")
    print(f"  Count of 'Abebe Kebede': {result2.count('Abebe Kebede')}")
    print(f"  ✅ PASS" if result2.count('Abebe Kebede') == 2 and '{name}' not in result2 else "  ❌ FAIL")
    print()
    
    # Test 3: No placeholder
    message3 = "Hello everyone, meeting at 3 PM"
    result3 = personalize_message(message3, "John Doe")
    print(f"Test 3 (No placeholder):")
    print(f"  Input:  {message3}")
    print(f"  Output: {result3}")
    print(f"  ✅ PASS" if result3 == message3 else "  ❌ FAIL")
    print()
    
    # Test 4: Empty name
    message4 = "Hello {name}, welcome!"
    result4 = personalize_message(message4, "")
    print(f"Test 4 (Empty name):")
    print(f"  Input:  {message4}")
    print(f"  Output: {result4}")
    print(f"  Result: '{result4}'")
    print()
    
    # Test 5: None name (edge case)
    message5 = "Hello {name}, welcome!"
    try:
        result5 = personalize_message(message5, None)
        print(f"Test 5 (None name):")
        print(f"  Input:  {message5}")
        print(f"  Output: {result5}")
        print(f"  ✅ PASS - Handled None gracefully" if result5 == message5 else "  ❌ FAIL")
    except Exception as e:
        print(f"Test 5 (None name):")
        print(f"  Error: {e}")
        print(f"  ❌ FAIL - Should handle None gracefully")
    print()


async def test_database_query():
    """Test if we can fetch users with full_name from database."""
    print("=" * 60)
    print("DATABASE QUERY TEST")
    print("=" * 60)
    
    try:
        from db.session import AsyncSessionLocal
        from db.models import User
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            # Fetch first 5 users to check their full_name
            stmt = select(User.user_id, User.username, User.full_name).limit(5)
            result = await session.execute(stmt)
            users = result.fetchall()
            
            print(f"\nFound {len(users)} users (showing first 5):")
            print("-" * 60)
            for user_id, username, full_name in users:
                print(f"  user_id: {user_id}")
                print(f"  username: {username}")
                print(f"  full_name: {full_name}")
                print(f"  full_name is None: {full_name is None}")
                print(f"  full_name is empty: {full_name == '' if full_name else 'N/A'}")
                print("-" * 60)
                
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("PERSONALIZATION FUNCTION TESTS")
    print("=" * 60)
    print()
    
    test_personalize_message()
    
    print("\n" + "=" * 60)
    print("Running database test...")
    print("=" * 60)
    asyncio.run(test_database_query())
