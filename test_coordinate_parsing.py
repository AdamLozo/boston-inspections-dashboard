"""
Quick test to verify coordinate parsing logic
Run this without needing database connection
"""

import re

def parse_coordinates(location: str) -> tuple:
    """
    Parse coordinates from location field in format: (latitude, longitude)
    Example: "(42.35108502118551, -71.0607889159121)"
    """
    if not location:
        return None, None

    try:
        # Extract coordinates from "(lat, lng)" format
        match = re.match(r'\(([0-9.-]+),\s*([0-9.-]+)\)', location.strip())
        if not match:
            return None, None

        lat = float(match.group(1))
        lng = float(match.group(2))

        # Validate Boston coordinates (rough bounding box)
        if 42.2 <= lat <= 42.4 and -71.2 <= lng <= -70.9:
            return lat, lng
        else:
            return None, None

    except (ValueError, AttributeError, TypeError) as e:
        return None, None


# Test cases
test_cases = [
    # Valid cases
    ("(42.35108502118551, -71.0607889159121)", (42.35108502118551, -71.0607889159121)),
    ("(42.3580012487741, -71.05424532932895)", (42.3580012487741, -71.05424532932895)),
    ("(42.26, -71.17)", (42.26, -71.17)),

    # Invalid cases
    (None, (None, None)),
    ("", (None, None)),
    ("invalid", (None, None)),
    ("(40.7128, -74.0060)", (None, None)),  # NYC coordinates (outside bounds)
    ("42.351, -71.060", (None, None)),  # Missing parentheses
]

print("Testing coordinate parsing...")
print("=" * 60)

passed = 0
failed = 0

for location, expected in test_cases:
    result = parse_coordinates(location)
    status = "PASS" if result == expected else "FAIL"

    if result == expected:
        passed += 1
    else:
        failed += 1

    print(f"[{status}] Input: {location}")
    if result != expected:
        print(f"  Expected: {expected}")
        print(f"  Got: {result}")

print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")

if failed == 0:
    print("All tests passed!")
else:
    print(f"{failed} test(s) failed")
