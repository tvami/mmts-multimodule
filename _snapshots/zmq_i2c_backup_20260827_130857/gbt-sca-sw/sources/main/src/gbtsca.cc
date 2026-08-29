#include <stdint.h>
#include <stdlib.h>
#include <cstring>
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>

#include <gbtsca_exception.h>
#include <uhal/uhal.hpp>
#include <gbtsca.h>

#include <vector>
#include <string>
#include <iostream>

using namespace uhal;

//uhal::ConnectionManager* GBT_SCA::g_manager=0;

GBT_SCA::GBT_SCA(const std::string& confile, const std::string& device, const std::string& basenode)
{
    //initialize the helper objects
    uhal::setLogLevelTo(Warning());

    try
    {
        manager_.reset( new ConnectionManager( confile.c_str() ) );
      
	ipbushw_.reset(new HwInterface(manager_->getDevice(device)));

	// Check for GBT SCA without triggering uhal error message
	if(ipbushw_->getNodes(basenode+".*").size() == 0)
	{
           THROW_SCA_EXCEPTION("GBT-SCA " + basenode + " not found ");
	}

	tx_= new Tx_helper(ipbushw_.get(), basenode);
	rx_= new Rx_helper(ipbushw_.get(), basenode);
	//resetHelper_= new Reset_helper(ipbushw_.get(), basenode);
    }
    catch(const uhal::exception::NoBranchFoundWithGivenUID& e)
    {
        THROW_SCA_EXCEPTION("Failed to find GBTSCA. uhal Error: " + std::string(e.what()));
    }

}

void GBT_SCA::transaction(const uint8_t& channel, const uint8_t& command, const uint8_t& data3, const uint8_t& data2, const uint8_t& data1, const uint8_t& data0, bool print)
{
    tx_->data.channel  = channel; 
    tx_->data.command  = command;

    tx_->data.data3 = data3;
    tx_->data.data2 = data2;
    tx_->data.data1 = data1;
    tx_->data.data0 = data0;

    uint8_t transID = tx_->push(true);

    if(print) tx_->print();

    do
    {
        if(rx_->fetch(true))
        {
            if(print) 
            {
                rx_->print();
                printf("\n");
            }
            rx_->pop();
        }
        else
        {
            THROW_SCA_HDLC_EXCEPTION("Timeout waiting on transaction " + std::to_string(transID), 0); 
        }
    }
    while(transID != rx_->data.transID);

    if(rx_->data.error) THROW_SCA_HDLC_EXCEPTION("", rx_->data.error);
}

void GBT_SCA::masked8BitWrite(const uint8_t channel, const uint8_t readCommand, const uint8_t writeCommand, const uint8_t mask, const uint8_t data)
{
    transaction(channel, readCommand);        
    transaction(channel, writeCommand, ((~mask) & rx_->data.data3) | (data & mask));        
}

void GBT_SCA::enableAdc(const bool enableADC)
{
    masked8BitWrite(CTRL_CONSTANTS::CHANNEL_CTRL, CTRL_CONSTANTS::R_CRD, CTRL_CONSTANTS::W_CRD, CTRL_CONSTANTS::MASK_CRD_ADC, enableADC?CTRL_CONSTANTS::MASK_CRD_ADC:0);
}

void GBT_SCA::enableI2C(const uint16_t enableI2Cs)
{
    const uint16_t INPUTMASK_CRB = 0x001f;
    const uint16_t INPUTMASK_CRC = 0x1fe0;
    const uint16_t INPUTMASK_CRD = 0xe000;

    if(enableI2Cs & INPUTMASK_CRB)
    {
        uint8_t data = ((1 << 0) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRB_I2C0:0;
        data        |= ((1 << 1) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRB_I2C1:0;
        data        |= ((1 << 2) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRB_I2C2:0;
        data        |= ((1 << 3) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRB_I2C3:0;
        data        |= ((1 << 4) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRB_I2C4:0;

        uint8_t mask = CTRL_CONSTANTS::MASK_CRB_I2C0 |  CTRL_CONSTANTS::MASK_CRB_I2C1 |  CTRL_CONSTANTS::MASK_CRB_I2C2 |  CTRL_CONSTANTS::MASK_CRB_I2C3 |  CTRL_CONSTANTS::MASK_CRB_I2C4;

        masked8BitWrite(CTRL_CONSTANTS::CHANNEL_CTRL, CTRL_CONSTANTS::R_CRB, CTRL_CONSTANTS::W_CRB, mask, data);
    }

    if(enableI2Cs & INPUTMASK_CRC)
    {
        uint8_t data = ((1 << 5)  & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C5:0;
        data        |= ((1 << 6)  & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C6:0;
        data        |= ((1 << 7)  & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C7:0;
        data        |= ((1 << 8)  & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C8:0;
        data        |= ((1 << 9)  & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C9:0;
        data        |= ((1 << 10) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C10:0;
        data        |= ((1 << 11) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C11:0;
        data        |= ((1 << 12) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRC_I2C12:0;

        uint8_t mask = CTRL_CONSTANTS::MASK_CRC_I2C5 |  CTRL_CONSTANTS::MASK_CRC_I2C6 |  CTRL_CONSTANTS::MASK_CRC_I2C7 |  CTRL_CONSTANTS::MASK_CRC_I2C8 | 
                       CTRL_CONSTANTS::MASK_CRC_I2C9 |  CTRL_CONSTANTS::MASK_CRC_I2C10 |  CTRL_CONSTANTS::MASK_CRC_I2C11 |  CTRL_CONSTANTS::MASK_CRC_I2C12;

        masked8BitWrite(CTRL_CONSTANTS::CHANNEL_CTRL, CTRL_CONSTANTS::R_CRC, CTRL_CONSTANTS::W_CRC, mask, data);
    }

    if(enableI2Cs & INPUTMASK_CRD)
    {
        uint8_t data = ((1 << 13) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRD_I2C13:0;
        data        |= ((1 << 14) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRD_I2C14:0;
        data        |= ((1 << 15) & enableI2Cs)?CTRL_CONSTANTS::MASK_CRD_I2C15:0;

        uint8_t mask = CTRL_CONSTANTS::MASK_CRD_I2C13 |  CTRL_CONSTANTS::MASK_CRD_I2C14 |  CTRL_CONSTANTS::MASK_CRD_I2C15;

        masked8BitWrite(CTRL_CONSTANTS::CHANNEL_CTRL, CTRL_CONSTANTS::R_CRD, CTRL_CONSTANTS::W_CRD, mask, data);
    }
}

uint32_t GBT_SCA::readDeviceID(bool v2)
{
    if(v2) transaction(CTRL_CONSTANTS::CHANNEL_ID, CTRL_CONSTANTS::R_CHIP_ID_V2);
    else   transaction(CTRL_CONSTANTS::CHANNEL_ID, CTRL_CONSTANTS::R_CHIP_ID_V1);

    return (static_cast<uint32_t>(rx_->data.data3) << 24) |
           (static_cast<uint32_t>(rx_->data.data2) << 16) |
           (static_cast<uint32_t>(rx_->data.data1) <<  8) |
            static_cast<uint32_t>(rx_->data.data0) ;
}

void GBT_SCA::i2cWrite(const uint8_t& bus, const uint8_t& address, const std::vector<uint8_t>& data )
{
//    printf("i2cWrite: %d, %d\n", bus, address);

    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::R_CTRL_REG);
    const uint8_t& ctrlBits = rx_->data.data3;

    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_CTRL_REG, (ctrlBits & ~I2C_CONSTANTS::MASK_CTRL_REG_NBYTE) | (data.size() << 2));
    
    if(     data.size() ==  1) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_0, data[0]);
    else if(data.size() ==  2) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_0, data[0], data[1]);
    else if(data.size() ==  3) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_0, data[0], data[1], data[2]);
    else if(data.size() <=  4) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_0, data[0], data[1], data[2], data[3]);

    if(     data.size() ==  5) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_1, data[4]);
    else if(data.size() ==  6) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_1, data[4], data[5]);
    else if(data.size() ==  7) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_1, data[4], data[5], data[6]);
    else if(data.size() <=  8) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_1, data[4], data[5], data[6], data[7]);

    if(     data.size() ==  9) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_2, data[8]);
    else if(data.size() == 10) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_2, data[8], data[9]);
    else if(data.size() == 11) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_2, data[8], data[9], data[10]);
    else if(data.size() <= 12) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_2, data[8], data[9], data[10], data[11]);

    if(     data.size() == 13) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_3, data[12]);
    else if(data.size() == 14) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_3, data[12], data[13]);
    else if(data.size() == 15) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_3, data[12], data[13], data[14]);
    else if(data.size() <= 16) transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_DATA_3, data[12], data[13], data[14], data[15]);

    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_7B_MULTI, address);
    bool error = rx_->data.data3 != 0x4;
    if(error)
    {
        THROW_SCA_I2C_EXCEPTION(rx_->data.data3);
    }
}

std::vector<uint8_t> GBT_SCA::i2cRead(const uint8_t& bus, const uint8_t& address, const uint8_t& nBytes )
{
//    printf("i2cRead: %d, %d, %d\n", bus, address, nBytes);

    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::R_CTRL_REG);
    const uint8_t& ctrlBits = rx_->data.data3;

    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_CTRL_REG, (ctrlBits & ~I2C_CONSTANTS::MASK_CTRL_REG_NBYTE) | (nBytes << 2));

    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_7B_MULTI, address);
    bool error = rx_->data.data3 != 0x4;
    if(error)
    {
        THROW_SCA_I2C_EXCEPTION(rx_->data.data3);
    }

    std::vector<uint8_t> reply;
    reply.reserve(nBytes);

    if(nBytes > 0)
    {
        transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::R_DATA_0);
        if(nBytes <= 1) reply.push_back(rx_->data.data3);
        if(nBytes <= 2) reply.push_back(rx_->data.data2);
        if(nBytes <= 3) reply.push_back(rx_->data.data1);
        if(nBytes <= 4) reply.push_back(rx_->data.data0);
    }
    if(nBytes > 4)
    {
        transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::R_DATA_1);
        if(nBytes <= 5) reply.push_back(rx_->data.data3);
        if(nBytes <= 6) reply.push_back(rx_->data.data2);
        if(nBytes <= 7) reply.push_back(rx_->data.data1);
        if(nBytes <= 8) reply.push_back(rx_->data.data0);
    }
    if(nBytes > 8)
    {
        transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::R_DATA_2);
        if(nBytes <= 9)  reply.push_back(rx_->data.data3);
        if(nBytes <= 10) reply.push_back(rx_->data.data2);
        if(nBytes <= 11) reply.push_back(rx_->data.data1);
        if(nBytes <= 12) reply.push_back(rx_->data.data0);
    }
    if(nBytes > 12)
    {
        transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::R_DATA_3);
        if(nBytes <= 13) reply.push_back(rx_->data.data3);
        if(nBytes <= 14) reply.push_back(rx_->data.data2);
        if(nBytes <= 15) reply.push_back(rx_->data.data1);
        if(nBytes <= 16) reply.push_back(rx_->data.data0);
    }

    return reply;
}

void GBT_SCA::i2cWrite_single(const uint8_t& bus, const uint8_t& address, const uint8_t& data )
{
    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::W_7B_SINGLE, address, data);
    bool error = rx_->data.data3 != 0x4;
    if(error)
    {
        THROW_SCA_I2C_EXCEPTION(rx_->data.data3);
    }
}

uint8_t GBT_SCA::i2cRead_single(const uint8_t& bus, const uint8_t& address)
{
    transaction(I2C_CONSTANTS::CHANNEL_MAP[bus], I2C_CONSTANTS::R_7B_SINGLE, address);
    bool error = rx_->data.data3 != 0x4;
    if(error)
    {
        THROW_SCA_I2C_EXCEPTION(rx_->data.data3);
    }
    return rx_->data.data2;
}

void GBT_SCA::gpioSetDirection(const uint32_t& direction)
{
    transaction(GPIO_CONSTANTS::CHANNEL, GPIO_CONSTANTS::W_DIRECTION,
                (0xff000000 & direction) >> 24,
                (0x00ff0000 & direction) >> 16,
                (0x0000ff00 & direction) >> 8,
                (0x000000ff & direction));
}

uint32_t GBT_SCA::gpioGetDirection()
{
    transaction(GPIO_CONSTANTS::CHANNEL, GPIO_CONSTANTS::R_DIRECTION);

    return static_cast<uint32_t>(rx_->data.data3) << 24 |
        static_cast<uint32_t>(rx_->data.data2) << 16 |
        static_cast<uint32_t>(rx_->data.data1) << 8 |
        static_cast<uint32_t>(rx_->data.data0);    
}

uint32_t GBT_SCA::gpioRead()
{
    transaction(GPIO_CONSTANTS::CHANNEL, GPIO_CONSTANTS::R_DATAIN);

    return static_cast<uint32_t>(rx_->data.data3) << 24 |
        static_cast<uint32_t>(rx_->data.data2) << 16 |
        static_cast<uint32_t>(rx_->data.data1) << 8 |
        static_cast<uint32_t>(rx_->data.data0);
}

uint8_t GBT_SCA::dacWrite(const char channel, uint8_t value)
{
    if(channel=='A'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::W_A, 0, 0, 0, value);}
    if(channel=='B'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::W_B, 0, 0, 0, value);}
    if(channel=='C'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::W_C, 0, 0, 0, value);}
    if(channel=='D'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::W_D, 0, 0, 0, value);}
     
    return static_cast<uint8_t>(rx_->data.data0);  
}

uint8_t GBT_SCA::dacRead(const char channel)
{
    if(channel=='A'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::R_A);}
    if(channel=='B'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::R_B);}
    if(channel=='C'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::R_C);}
    if(channel=='D'){transaction(DAC_CONSTANTS::CHANNEL, DAC_CONSTANTS::R_D);}
     
    return static_cast<uint8_t>(rx_->data.data0);  
}

uint16_t GBT_SCA::adcRead(int channel) 
{

    transaction(ADC_CONSTANTS::CHANNEL, ADC_CONSTANTS::W_MUX_REG, 0, 0, 0, channel&0xFF);
    //         printf("Step 1 done\n");
    try {
        transaction(ADC_CONSTANTS::CHANNEL, ADC_CONSTANTS::GO_REG, 0, 0, 0, 1);
    } catch (GBT_SCA_HDLC_Exception& e) {
        printf("ADC did not reply -- generally locks up the SCA, requiring a hard reset.\n");
        throw e; // now we can throw it again..
    }
//         printf("%x %x %x %x\n",rx_->data.data3,rx_->data.data2,rx_->data.data1,rx_->data.data0);
    return (rx_->data.data1<<8)|(rx_->data.data0);
}
void GBT_SCA::gpioWrite(const uint32_t& data, const uint32_t& mask)
{
    masked32BitWrite(GPIO_CONSTANTS::CHANNEL, GPIO_CONSTANTS::R_DATAOUT, GPIO_CONSTANTS::W_DATAOUT, mask, data);
}

void GBT_SCA::masked32BitWrite(const uint8_t channel, const uint8_t readCommand, const uint8_t writeCommand, const uint32_t mask, const uint32_t data)
{
    const uint8_t& d0 = reinterpret_cast<const uint8_t*>(&data)[0];
    const uint8_t& d1 = reinterpret_cast<const uint8_t*>(&data)[1];
    const uint8_t& d2 = reinterpret_cast<const uint8_t*>(&data)[2];
    const uint8_t& d3 = reinterpret_cast<const uint8_t*>(&data)[3];

    const uint8_t& m0 = reinterpret_cast<const uint8_t*>(&mask)[0];
    const uint8_t& m1 = reinterpret_cast<const uint8_t*>(&mask)[1];
    const uint8_t& m2 = reinterpret_cast<const uint8_t*>(&mask)[2];
    const uint8_t& m3 = reinterpret_cast<const uint8_t*>(&mask)[3];

    transaction(channel, readCommand);
    transaction(channel, writeCommand, ((~m3) & rx_->data.data3) | (d3 & m3), ((~m2) & rx_->data.data2) | (d2 & m2), ((~m1) & rx_->data.data1) | (d1 & m1), ((~m0) & rx_->data.data0) | (d0 & m0));
}

void GBT_SCA::enableGPIO(const bool enableGPIO)
{
    masked8BitWrite(CTRL_CONSTANTS::CHANNEL_CTRL, CTRL_CONSTANTS::R_CRB, CTRL_CONSTANTS::W_CRB, CTRL_CONSTANTS::MASK_CRB_PARAL, enableGPIO?CTRL_CONSTANTS::MASK_CRB_PARAL:0);
}

void GBT_SCA::setI2CSpeed(const uint8_t i2cBus, const uint8_t speed)
{
    masked8BitWrite(I2C_CONSTANTS::CHANNEL_MAP[i2cBus], I2C_CONSTANTS::R_CTRL_REG, I2C_CONSTANTS::W_CTRL_REG, I2C_CONSTANTS::MASK_CTRL_REG_SPEED, speed);
}


void GBT_SCA::setI2CSCLMode(const uint8_t i2cBus, const bool directDrive)
{
    masked8BitWrite(I2C_CONSTANTS::CHANNEL_MAP[i2cBus], I2C_CONSTANTS::R_CTRL_REG, I2C_CONSTANTS::W_CTRL_REG, I2C_CONSTANTS::MASK_CTRL_REG_SCLDRIVE, directDrive?I2C_CONSTANTS::MASK_CTRL_REG_SCLDRIVE:0);
}
