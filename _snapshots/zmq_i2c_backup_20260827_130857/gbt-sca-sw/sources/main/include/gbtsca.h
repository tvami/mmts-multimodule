#ifndef GBTSCA_MAIN
#define GBTSCA_MAIN

#include <stdint.h>

#include <uhal/uhal.hpp>
#include <gbtsca_txhelper.h>
#include <gbtsca_rxhelper.h>
#include <gbtsca_resethelper.h>
#include <gbtsca_exception.h>
#include <string>
#include <vector>
#include <memory>

using namespace uhal;

namespace CTRL_CONSTANTS
{
    // Channels 
    static constexpr uint8_t CHANNEL_CTRL = 0x00;
    static constexpr uint8_t CHANNEL_ID   = 0x14;
    static constexpr uint8_t CHANNEL_SEC  = 0x13;

    //commands
    static constexpr uint8_t W_CRB = 0x2;
    static constexpr uint8_t W_CRC = 0x4;
    static constexpr uint8_t W_CRD = 0x6;

    static constexpr uint8_t R_CRB = 0x3;
    static constexpr uint8_t R_CRC = 0x5;
    static constexpr uint8_t R_CRD = 0x7;

    static constexpr uint8_t R_SEU = 0xf1;
    static constexpr uint8_t SEU_RESET = 0xf0;

    static constexpr uint8_t R_CHIP_ID_V1 = 0xd1;
    static constexpr uint8_t R_CHIP_ID_V2 = 0x91;

    static constexpr uint8_t MASK_CRB_SPI   = 0x02;
    static constexpr uint8_t MASK_CRB_PARAL = 0x04;
    static constexpr uint8_t MASK_CRB_I2C0  = 0x08;
    static constexpr uint8_t MASK_CRB_I2C1  = 0x10;
    static constexpr uint8_t MASK_CRB_I2C2  = 0x20;
    static constexpr uint8_t MASK_CRB_I2C3  = 0x40;
    static constexpr uint8_t MASK_CRB_I2C4  = 0x80;

    static constexpr uint8_t MASK_CRC_I2C5  = 0x01;
    static constexpr uint8_t MASK_CRC_I2C6  = 0x02;
    static constexpr uint8_t MASK_CRC_I2C7  = 0x04;
    static constexpr uint8_t MASK_CRC_I2C8  = 0x08;
    static constexpr uint8_t MASK_CRC_I2C9  = 0x10;
    static constexpr uint8_t MASK_CRC_I2C10 = 0x20;
    static constexpr uint8_t MASK_CRC_I2C11 = 0x40;
    static constexpr uint8_t MASK_CRC_I2C12 = 0x80;

    static constexpr uint8_t MASK_CRD_I2C13 = 0x01;
    static constexpr uint8_t MASK_CRD_I2C14 = 0x02;
    static constexpr uint8_t MASK_CRD_I2C15 = 0x04;
    static constexpr uint8_t MASK_CRD_JTAG  = 0x08;
    static constexpr uint8_t MASK_CRD_ADC   = 0x10;
    static constexpr uint8_t MASK_CRD_DAC   = 0x40;
}
namespace DAC_CONSTANTS
{
    static constexpr uint8_t CHANNEL     = 0x15;
    static constexpr uint8_t W_A     = 0x10;
    static constexpr uint8_t R_A     = 0x11;
    static constexpr uint8_t W_B     = 0x20;
    static constexpr uint8_t R_B     = 0x21;
    static constexpr uint8_t W_C     = 0x30;
    static constexpr uint8_t R_C     = 0x31;
    static constexpr uint8_t W_D     = 0x40;
    static constexpr uint8_t R_D     = 0x41;
}
namespace ADC_CONSTANTS
{
    static constexpr uint8_t CHANNEL     = 0x14;
    static constexpr uint8_t GO_REG      = 0x02;
    static constexpr uint8_t W_MUX_REG   = 0x50;
    static constexpr uint8_t R_MUX_REG   = 0x51;

}
namespace I2C_CONSTANTS
{
    // I2C occupies 16 channels from 0x3 to 0x12
    static constexpr uint8_t CHANNEL_MAP[] = {0x3, 0x4, 0x5, 0x6, 0x7, 0x8, 0x9, 0xa, 0xb, 0xc, 0xd, 0xe, 0xf, 0x10, 0x11, 0x12};

    //commands
    static constexpr uint8_t W_CTRL_REG = 0x30;
    static constexpr uint8_t R_CTRL_REG = 0x31;
    static constexpr uint8_t R_STATUS_REG = 0x11;
    static constexpr uint8_t W_MASK = 0x20;
    static constexpr uint8_t R_MASK = 0x21;
    static constexpr uint8_t W_DATA_0 = 0x40;
    static constexpr uint8_t R_DATA_0 = 0x41;
    static constexpr uint8_t W_DATA_1 = 0x50;
    static constexpr uint8_t R_DATA_1 = 0x51;
    static constexpr uint8_t W_DATA_2 = 0x60;
    static constexpr uint8_t R_DATA_2 = 0x61;
    static constexpr uint8_t W_DATA_3 = 0x70;
    static constexpr uint8_t R_DATA_3 = 0x71;
    static constexpr uint8_t W_7B_SINGLE = 0x82;
    static constexpr uint8_t R_7B_SINGLE = 0x86;
    static constexpr uint8_t W_7B_MULTI = 0xDA;
    static constexpr uint8_t R_7B_MULTI = 0xDE;
    static constexpr uint8_t W_10B_SINGLE = 0x82;
    static constexpr uint8_t R_10B_SINGLE = 0x86;
    static constexpr uint8_t W_10B_MULTI = 0xDA;
    static constexpr uint8_t R_10B_MULTI = 0xDE;

    //bit masks 
    static constexpr uint8_t MASK_CTRL_REG_SCLDRIVE = 0x80;
    static constexpr uint8_t MASK_CTRL_REG_NBYTE = 0x7c;
    static constexpr uint8_t MASK_CTRL_REG_SPEED = 0x03;
};

namespace GPIO_CONSTANTS
{
    static constexpr uint8_t CHANNEL = 0x02;

    static constexpr uint8_t W_DATAOUT = 0x10;
    static constexpr uint8_t R_DATAOUT = 0x11;
    static constexpr uint8_t R_DATAIN = 0x01;
    static constexpr uint8_t W_DIRECTION = 0x20;
    static constexpr uint8_t R_DIRECTION = 0x21;
    static constexpr uint8_t W_INT_ENABLE = 0x60;
    static constexpr uint8_t R_INT_ENABLE = 0x61;
    static constexpr uint8_t W_INT_SEL = 0x30;
    static constexpr uint8_t R_INT_SEL = 0x31;
    static constexpr uint8_t W_INT_TRIG = 0x40;
    static constexpr uint8_t R_INT_TRIG = 0x41;
    static constexpr uint8_t W_INTS = 0x70;
    static constexpr uint8_t R_INTS = 0x71;
    static constexpr uint8_t W_CLKSEL = 0x80;
    static constexpr uint8_t R_CLKSEL = 0x81;
    static constexpr uint8_t W_EDGESEL = 0x90;
    static constexpr uint8_t R_EDGESEL = 0x91;
};


class GBT_SCA
{
public://private:
    Tx_helper* tx_;
    Rx_helper* rx_;
    Reset_helper* resetHelper_;
    std::unique_ptr<ConnectionManager> manager_;
    std::unique_ptr<HwInterface> ipbushw_ ;

public:
    GBT_SCA(const std::string& confile, const std::string& device, const std::string& basenode);
    void reset() {resetHelper_->reset();}
    void softReset() {}//tx_->softReset();}
    void transaction(const uint8_t& channel, const uint8_t& command, const uint8_t& data3 = 0, const uint8_t& data2 = 0, const uint8_t& data1 = 0, const uint8_t& data0 = 0, bool print = false);
    void masked8BitWrite(const uint8_t channel, const uint8_t readCommand, const uint8_t writeCommand, const uint8_t mask, const uint8_t data);
    void enableAdc(const bool enableADC);
    uint16_t adcRead(int channel);
    void enableI2C(const uint16_t enableI2Cs);
    uint32_t readDeviceID(bool v2 = false);
    void i2cWrite(const uint8_t& bus, const uint8_t& address, const std::vector<uint8_t>& data );
    std::vector<uint8_t> i2cRead(const uint8_t& bus, const uint8_t& address, const uint8_t& nBytes );
    void i2cWrite_single(const uint8_t& bus, const uint8_t& address, const uint8_t& data );
    uint8_t i2cRead_single(const uint8_t& bus, const uint8_t& address);
    void gpioSetDirection(const uint32_t& direction);
    uint32_t gpioGetDirection();
    uint32_t gpioRead();
    uint8_t dacWrite(const char channel, const uint8_t value);
    uint8_t dacRead(const char channel);
    void gpioWrite(const uint32_t& data, const uint32_t& mask);
    void masked32BitWrite(const uint8_t channel, const uint8_t readCommand, const uint8_t writeCommand, const uint32_t mask, const uint32_t data);
    void enableGPIO(const bool enableGPIO);
    void setI2CSpeed(const uint8_t i2cBus, const uint8_t speed);
    void setI2CSCLMode(const uint8_t i2cBus, const bool directDrive);
};

#endif
