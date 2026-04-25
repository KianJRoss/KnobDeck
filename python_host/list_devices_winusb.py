"""
List all HID devices (pywinusb) and highlight likely KnobDeck-compatible keyboards.
"""

import pywinusb.hid as hid

print("Enumerating all HID devices...")
print("=" * 80)

all_devices = hid.find_all_hid_devices()
matching_devices = []

for device in all_devices:
    vid = device.vendor_id
    pid = device.product_id
    manufacturer = device.vendor_name
    product = device.product_name

    print(f"VID: 0x{vid:04X}  PID: 0x{pid:04X}")
    print(f"  Manufacturer: {manufacturer}")
    print(f"  Product: {product}")
    print(f"  Path: {device.device_path}")
    print()

    manufacturer_l = (manufacturer or "").lower()
    if any(x in manufacturer_l for x in ["keychron", "monsgeek", "epomaker", "ajazz", "feker"]):
        matching_devices.append(device)

print("=" * 80)

if matching_devices:
    print(f"\nFound {len(matching_devices)} likely compatible device(s):")
    for device in matching_devices:
        print(f"  VID: 0x{device.vendor_id:04X}, PID: 0x{device.product_id:04X}")
        print(f"  Product: {device.product_name}")
        print(f"  Path: {device.device_path}")
        print()

    print("\nUse these values in your keyboard profile:")
    device = matching_devices[0]
    print(f"VENDOR_ID = 0x{device.vendor_id:04X}")
    print(f"PRODUCT_ID = 0x{device.product_id:04X}")
else:
    print("\nNo likely compatible devices found.")
    print("Make sure the keyboard is connected and firmware is flashed.")
