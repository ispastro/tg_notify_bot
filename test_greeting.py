"""Test automatic greeting personalization."""
import sys
import io
from utils.message_utils import personalize_message

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("AUTOMATIC GREETING TEST")
print("=" * 60)
print()

# Test 1: Amharic message
message1 = """ዛሬ ጸሎት፣ መዝሙር ጨዋታ ና ሌሎችንም መርሃ ግብራትን  
ያካተተ ልዩ የቤተሰብ👨👩👧👧 ጉባኤ አለ::
📍 የት? ማኅበረ ቅዱሳን ሕንጻ 3ኛ ፎቅ
🕐 መቼ? ዛሬ 11፡30"""

result1 = personalize_message(message1, "Haile A")
print("Test 1: Haile A receives:")
print("-" * 60)
print(result1)
print("-" * 60)
print()

result2 = personalize_message(message1, "Abebe Kebede")
print("Test 2: Abebe Kebede receives:")
print("-" * 60)
print(result2)
print("-" * 60)
print()

# Test 3: English message
message3 = "Meeting today at 3 PM. Don't be late!"
result3 = personalize_message(message3, "John Doe")
print("Test 3: John Doe receives:")
print("-" * 60)
print(result3)
print("-" * 60)
print()

# Test 4: No name (should return original)
result4 = personalize_message(message1, None)
print("Test 4: User with no name receives:")
print("-" * 60)
print(result4)
print("-" * 60)
print()

print("✅ All tests completed!")
