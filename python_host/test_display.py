"""
Test Display Control Features
Quick diagnostic tool to check brightness and monitor detection
"""

import win32api
import win32con
import pywintypes
import subprocess
import sys

# Windows display device state flags
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
DISPLAY_DEVICE_ACTIVE = 0x00000001

print("=" * 60)
print("Display Control Diagnostic Tool")
print("=" * 60)
print()

# Test 1: Enumerate Monitors
print("1. Testing Monitor Enumeration")
print("-" * 60)

monitors = []
device_num = 0

while True:
    try:
        device = win32api.EnumDisplayDevices(None, device_num, 0)
        device_name = device.DeviceName

        print(f"\nDevice {device_num}: {device_name}")
        print(f"  Description: {device.DeviceString}")
        print(f"  State Flags: {device.StateFlags} (0x{device.StateFlags:08X})")

        # Check flags
        attached = bool(device.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP)
        active = bool(device.StateFlags & DISPLAY_DEVICE_ACTIVE)
        primary = bool(device.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE)

        print(f"  - Attached to Desktop: {attached}")
        print(f"  - Active: {active}")
        print(f"  - Primary: {primary}")

        if attached:
            try:
                settings = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)
                print(f"  - Resolution: {settings.PelsWidth}x{settings.PelsHeight}")
                print(f"  - Position: ({settings.Position_x}, {settings.Position_y})")
                print(f"  - Refresh Rate: {settings.DisplayFrequency}Hz")

                monitors.append({
                    'device_name': device_name,
                    'device_string': device.DeviceString,
                    'active': active
                })
            except Exception as e:
                print(f"  - Error getting settings: {e}")

        device_num += 1

    except pywintypes.error:
        break

print(f"\nTotal devices found: {device_num}")
print(f"Monitors that can be toggled: {len(monitors)}")

# Test 2: Brightness Control
print("\n" + "=" * 60)
print("2. Testing Brightness Control")
print("-" * 60)

print("\nReading current brightness...")
try:
    ps_command = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
    result = subprocess.run(
        ["powershell", "-Command", ps_command],
        capture_output=True,
        timeout=3,
        text=True
    )

    if result.returncode == 0 and result.stdout.strip():
        current = int(result.stdout.strip())
        print(f"✓ Current brightness: {current}%")

        # Test setting brightness
        print("\nTesting brightness adjustment...")
        print("  Attempting to set brightness to 60%...")

        ps_set = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,60)"
        result2 = subprocess.run(
            ["powershell", "-Command", ps_set],
            capture_output=True,
            timeout=3,
            text=True
        )

        if result2.returncode == 0:
            print("✓ Brightness control works!")

            # Read again to verify
            result3 = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                timeout=3,
                text=True
            )

            if result3.returncode == 0 and result3.stdout.strip():
                new_brightness = int(result3.stdout.strip())
                print(f"  New brightness: {new_brightness}%")

            # Restore original
            ps_restore = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{current})"
            subprocess.run(["powershell", "-Command", ps_restore], capture_output=True, timeout=3)
            print(f"  Restored to original: {current}%")
        else:
            print(f"✗ Failed to set brightness")
            print(f"  Error: {result2.stderr}")
    else:
        print(f"✗ Could not read brightness")
        print(f"  Return code: {result.returncode}")
        print(f"  Output: {result.stdout}")
        print(f"  Error: {result.stderr}")
        print("\n  This usually means:")
        print("  - External monitor (not laptop screen)")
        print("  - Brightness control not supported")
        print("  - WMI service not running")

except subprocess.TimeoutExpired:
    print("✗ Brightness check timed out")
except Exception as e:
    print(f"✗ Error: {e}")

# Summary
print("\n" + "=" * 60)
print("Summary")
print("=" * 60)

if len(monitors) > 0:
    print(f"✓ Monitor toggle should work ({len(monitors)} monitor(s))")
else:
    print("✗ Monitor toggle may not work (no monitors detected)")
    print("  Try running as Administrator")

print("\nFor more details, check:")
print("  python_host/logs/knobdeck_app.log")

print("\n" + "=" * 60)
input("Press Enter to exit...")
