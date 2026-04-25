"""
List all HID devices and highlight likely KnobDeck-compatible keyboards.
"""

import hid

print("Enumerating all HID devices...")
print("=" * 80)

devices = hid.enumerate()
matching_devices = []

for device in devices:
    vid = device['vendor_id']
    pid = device['product_id']
    manufacturer = device['manufacturer_string']
    product = device['product_string']
    interface = device['interface_number']
    usage_page = device['usage_page']
    usage = device['usage']

    print(f"VID: 0x{vid:04X}  PID: 0x{pid:04X}  Interface: {interface}")
    print(f"  Manufacturer: {manufacturer}")
    print(f"  Product: {product}")
    print(f"  Usage Page: 0x{usage_page:04X}  Usage: 0x{usage:04X}")
    print()

    manufacturer_l = (manufacturer or "").lower()
    if any(x in manufacturer_l for x in ["keychron", "monsgeek", "epomaker", "ajazz", "feker"]):
        matching_devices.append(device)

print("=" * 80)

if matching_devices:
    print(f"\nFound {len(matching_devices)} likely compatible device(s):")
    for device in matching_devices:
        print(f"  VID: 0x{device['vendor_id']:04X}, PID: 0x{device['product_id']:04X}")
        print(f"  Interface: {device['interface_number']}")
        print(f"  Usage Page: 0x{device['usage_page']:04X}")
        print(f"  Product: {device['product_string']}")
        print()

    print("\nUse these values in your keyboard profile:")
    device = matching_devices[0]
    print(f"VENDOR_ID = 0x{device['vendor_id']:04X}")
    print(f"PRODUCT_ID = 0x{device['product_id']:04X}")
else:
    print("\nNo likely compatible devices found.")
    print("Make sure the keyboard is connected and firmware is flashed.")
