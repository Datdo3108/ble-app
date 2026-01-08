import asyncio
import time
from bleak import BleakScanner, BleakClient

async def scan_and_list_devices():
    devices = await BleakScanner.discover()
    device_dict = {device.name: device for device in devices if device.name}
    for name, device in device_dict.items():
        print(f"{name} [{device.address}]")
    return device_dict

async def discover_services_and_characteristics(address):
    async with BleakClient(address) as client:
        services = await client.get_services()
        for service in services:
            print(f"Service: {service.uuid}")
            for char in service.characteristics:
                print(f"  Characteristic: {char.uuid} - Properties: {char.properties}")

async def read_data(address, char_uuid):
    async with BleakClient(address) as client:
        value = await client.read_gatt_char(char_uuid)
        print("Read value: ", value)

#### Notification to read data
async def notification_handler(sender, data):
    print(f"Notification from {sender}: {data}")

async def enable_notifications(address, char_uuid):
    async with BleakClient(address) as client:
        await client.start_notify(char_uuid, notification_handler)
        await asyncio.sleep(30)  # Keep the notification handler active for 30 seconds
        await client.stop_notify(char_uuid)
####

async def main():
    while True:
        device_dict = await scan_and_list_devices()
        if not device_dict:
            print("No devices found")
            return

        device_name = input("Enter the device name to connect to: ")
        if device_name in device_dict:
            break
        else:
            print("Device not found. Scanning again...")

    device = device_dict[device_name]
    print(f"Connecting to {device.name} [{device.address}]")

    await discover_services_and_characteristics(device.address)
    
    characteristic_uuid = input("Enter characteristics UUID want to read: ")  # Replace with your characteristic UUID
    await read_data(device.address, characteristic_uuid)


# Run the main function
asyncio.run(main())
