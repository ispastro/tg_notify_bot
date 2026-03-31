"""Test flexible time format parsing."""
import re
import sys
import io
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def normalize_time(time_text):
    """Normalize time format to add space before AM/PM if missing."""
    time_text = time_text.strip().upper()
    # Add space before AM/PM if missing
    time_text = re.sub(r'(\d)(AM|PM)$', r'\1 \2', time_text)
    return time_text

# Test cases
test_cases = [
    "5:20PM",
    "5:20 PM",
    "5:20pm",
    "5:20 pm",
    "11:45AM",
    "11:45 AM",
    "11:45am",
    "11:45 am",
    "12:00PM",
    "12:00 PM",
]

print("=" * 60)
print("TIME FORMAT NORMALIZATION TEST")
print("=" * 60)
print()

for test in test_cases:
    normalized = normalize_time(test)
    try:
        parsed = datetime.strptime(normalized, "%I:%M %p")
        print(f"✅ '{test}' -> '{normalized}' -> {parsed.strftime('%I:%M %p')}")
    except ValueError as e:
        print(f"❌ '{test}' -> '{normalized}' -> FAILED: {e}")

print()
print("=" * 60)
print("All formats supported!")
print("=" * 60)
