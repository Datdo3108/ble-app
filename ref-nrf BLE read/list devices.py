import asyncio
from bleak import BleakScanner, BleakClient

async def main():
    myDevice = ''
    devices = await BleakScanner.discover(5.0, return_adv=True)
    for d in devices:
        if(devices[d][1].local_name == 'FSEMI1'):
            print("Found it")
            myDevice = d

        print(devices[d][1].local_name)

    address = myDevice
    async with BleakClient(address) as client:
        svcs = client.services
        print("Services:")
        for service in svcs:
            print(service)


asyncio.run(main())