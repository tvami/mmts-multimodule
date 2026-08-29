import gbtsca_bus
import uhal


def rocSetAddress(i2cbus, i2cAddr, addr):
    addr_low = addr & ((1 << 8)-1)
    addr_high = addr >> 8
    i2cbus.write_byte(i2cAddr | 0x0, addr_low)
    i2cbus.write_byte(i2cAddr | 0x1, addr_high)

# Initialize with existing uhal HwInterface
uhal.setLogLevelTo(uhal.LogLevel.WARNING)
manager = uhal.ConnectionManager("file://${UHAL_ADDRESS_TABLE}/connection.xml")
ipbushw = uhal.HwInterface(manager.getDevice("mylittlememory"))
sca = gbtsca_bus.GBTSCA("gbt_sca_com_0", Interface=ipbushw)

# Initialize with connection file + device name
#sca = gbtsca_bus.GBTSCA("gbt_sca_com_0","file://${UHAL_ADDRESS_TABLE}/connection.xml", "jeremylittlememory")
#devId = sca.readDeviceID()


devId = sca.readDeviceID()
print(devId)
