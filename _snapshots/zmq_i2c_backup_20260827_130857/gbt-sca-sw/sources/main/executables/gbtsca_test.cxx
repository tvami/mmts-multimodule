#include <stdint.h>
#include <errno.h>

#include <gbtsca.h>

void rocSetAddress(GBT_SCA& sca, const uint8_t& i2cBus, const uint8_t& i2cAddr, const uint16_t& addr)
{
    const uint8_t& addr_low = reinterpret_cast<const uint8_t*>(&addr)[0];
    const uint8_t& addr_high = reinterpret_cast<const uint8_t*>(&addr)[1];

    sca.i2cWrite_single(i2cBus, i2cAddr | 0x0, addr_low);
    sca.i2cWrite_single(i2cBus, i2cAddr | 0x1, addr_high);
}

int main(int argc, char** argv)
{
    try
    {
        std::string confile = "file://connections.xml";
	std::string device = "mylittlememory";
	std::string node = "gbt_sca_com_1";

        GBT_SCA sca(confile, device, node);

        sca.enableAdc(true);

        uint32_t devId = sca.readDeviceID();
        printf("Device ID: %08x\n", devId);
    }
    catch(const GBT_SCA_I2C_Exception& e)
    {
        e.print();
    }
    catch(const GBT_SCA_HDLC_Exception& e)
    {
        e.print();
    }
}
