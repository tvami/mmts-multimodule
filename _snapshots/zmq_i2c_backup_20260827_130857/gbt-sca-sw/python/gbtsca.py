import uhal
import gbtsca_rxhelper
import gbtsca_txhelper
import gbtsca_resethelper
import gbtsca_exception
import gbtsca_constants
import sys


class GBT_SCA:
    def __init__(self, basenode, confile=None, device=None, hwInterface=None):
        uhal.setLogLevelTo(uhal.LogLevel.WARNING)

        try:
            if hwInterface is None:
                self.manager = uhal.ConnectionManager(confile)
                self.ipbushw = uhal.HwInterface(self.manager.getDevice(device))
            else:
                self.ipbushw = hwInterface
            # Check for GBT SCA without triggering uhal error message
            if(len(self.ipbushw.getNodes(basenode+".*")) == 0):
                raise gbtsca_exception.GBT_SCA_Exception(
                    sys._getframe().f_lineno, "__init__", "GBT-SCA " + basenode + " not found ")
            self.tx = gbtsca_txhelper.Tx_helper(self.ipbushw, basenode)
            self.rx = gbtsca_rxhelper.Rx_helper(self.ipbushw, basenode)
            self.resethelper = gbtsca_resethelper.gbtsca_resethelper(
                self.ipbushw, basenode)
        except uhal.exception as uhalerr:  # Fix error throwing
            print(uhalerr)
            raise gbtsca_exception.GBT_SCA_Exception(
                sys._getframe().f_lineno, "__init__", "gbtsca.py", "Failed to find GBTSCA.")

    def transaction(self, channel, command, data3=0, data2=0, data1=0, data0=0, doprint=False):
        self.tx.data.channel = channel
        self.tx.data.command = command
        self.tx.data.data3 = data3
        self.tx.data.data2 = data2
        self.tx.data.data1 = data1
        self.tx.data.data0 = data0

        transID = self.tx.push(True)

        if(doprint):
            self.tx.txprint()

        dataRecieved = False
        while not dataRecieved:
            if(self.rx.fetch(True)):
                if(doprint):
                    self.rx.rxprint()
                self.rx.pop()
            else:
                raise gbtsca_exception.GBT_SCA_HDLC_Exception(sys._getframe(
                ).f_lineno, "transaction", "gbtsca.py", "Timeout waiting on transaction " + str(transID), 0)
            if transID == self.rx.data.transID:
                dataRecieved = True

        if(self.rx.data.error):
            raise gbtsca_exception.GBT_SCA_HDLC_Exception(
                sys._getframe().f_lineno, "transaction", "gbtsca.py", "", self.rx.data.error)

    def masked8BitWrite(self, channel, readCommand, writeCommand, mask, data):
        self.transaction(channel, readCommand)
        self.transaction(channel, writeCommand, ((~mask) &
                                                 self.rx.data.data3) | (data & mask))

    def enableAdc(self, enableADC):
        self.masked8BitWrite(gbtsca_constants.CTRL["CHANNEL_CTRL"], gbtsca_constants.CTRL["R_CRD"],
                             gbtsca_constants.CTRL["W_CRD"],
                             gbtsca_constants.CTRL["MASK_CRD_ADC"], gbtsca_constants.CTRL["MASK_CRD_ADC"] if enableADC else 0)


    def enableDAC(self, enableDAC):
        self.masked8BitWrite(gbtsca_constants.CTRL["CHANNEL_CTRL"], gbtsca_constants.CTRL["R_CRD"],
                             gbtsca_constants.CTRL["W_CRD"],
                             gbtsca_constants.CTRL["MASK_CRD_DAC"], gbtsca_constants.CTRL["MASK_CRD_DAC"] if enableDAC else 0)

    def enableI2C(self, enableI2Cs):
        INPUTMASK_CRB = 0x001f
        INPUTMASK_CRC = 0x1fe0
        INPUTMASK_CRD = 0xe000

        if(enableI2Cs & INPUTMASK_CRB):
            data = 0
            if((1 << 0) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRB_I2C0"]
            if((1 << 1) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRB_I2C1"]
            if((1 << 2) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRB_I2C2"]
            if((1 << 3) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRB_I2C3"]
            if((1 << 4) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRB_I2C4"]

            mask = gbtsca_constants.CTRL["MASK_CRB_I2C0"] | gbtsca_constants.CTRL["MASK_CRB_I2C1"] | gbtsca_constants.CTRL[
                "MASK_CRB_I2C2"] | gbtsca_constants.CTRL["MASK_CRB_I2C3"] | gbtsca_constants.CTRL["MASK_CRB_I2C4"]

            self.masked8BitWrite(gbtsca_constants.CTRL["CHANNEL_CTRL"],
                                 gbtsca_constants.CTRL["R_CRB"], gbtsca_constants.CTRL["W_CRB"], mask, data)

        if(enableI2Cs & INPUTMASK_CRC):
            data = 0
            if((1 << 5) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C5"]
            if((1 << 6) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C6"]
            if((1 << 7) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C7"]
            if((1 << 8) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C8"]
            if((1 << 9) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C9"]
            if((1 << 10) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C10"]
            if((1 << 11) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C11"]
            if((1 << 12) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRC_I2C12"]

            mask = gbtsca_constants.CTRL["MASK_CRC_I2C5"] | gbtsca_constants.CTRL["MASK_CRC_I2C6"] | gbtsca_constants.CTRL["MASK_CRC_I2C7"] | gbtsca_constants.CTRL[
                "MASK_CRC_I2C8"] | gbtsca_constants.CTRL["MASK_CRC_I2C9"] | gbtsca_constants.CTRL["MASK_CRC_I2C10"] | gbtsca_constants.CTRL["MASK_CRC_I2C11"] | gbtsca_constants.CTRL["MASK_CRC_I2C12"]

            self.masked8BitWrite(gbtsca_constants.CTRL["CHANNEL_CTRL"],
                                 gbtsca_constants.CTRL["R_CRC"], gbtsca_constants.CTRL["W_CRC"], mask, data)

        if(enableI2Cs & INPUTMASK_CRD):
            data = 0
            if((1 << 13) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRD_I2C13"]
            if((1 << 14) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRD_I2C14"]
            if((1 << 15) & enableI2Cs):
                data = data | gbtsca_constants.CTRL["MASK_CRD_I2C15"]

            mask = gbtsca_constants.CTRL["MASK_CRD_I2C13"] | gbtsca_constants.CTRL[
                "MASK_CRD_I2C14"] | gbtsca_constants.CTRL["MASK_CRD_I2C15"]

            self.masked8BitWrite(gbtsca_constants.CTRL["CHANNEL_CTRL"],
                                 gbtsca_constants.CTRL["R_CRD"], gbtsca_constants.CTRL["W_CRD"], mask, data)

    def readDeviceID(self, v2=False):
        if(v2):
            self.transaction(gbtsca_constants.CTRL["CHANNEL_ID"],
                             gbtsca_constants.CTRL["R_CHIP_ID_V2"])
        else:
            self.transaction(gbtsca_constants.CTRL["CHANNEL_ID"],
                             gbtsca_constants.CTRL["R_CHIP_ID_V1"])

        return (self.rx.data.data3 << 24) | (self.rx.data.data2 << 16) | (self.rx.data.data1 << 8) | self.rx.data.data0

    def i2cWrite(self, bus, address, data):
        #print("i2cWrite: "+bus+", "+address+"\n")
        self.transaction(
            gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["R_CTRL_REG"])
        ctrlBits = self.rx.data.data3

        self.transaction(gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_CTRL_REG"], (
            ctrlBits & ~gbtsca_constants.I2C["MASK_CTRL_REG_NBYTE"]) | (data.size() << 2))

        if(data.size() == 1):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_0"], data[0])
        elif(data.size() == 2):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_0"], data[0], data[1])
        elif(data.size() == 3):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_0"], data[0], data[1], data[2])
        elif(data.size() <= 4):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_0"], data[0], data[1], data[2], data[3])

        if(data.size() == 5):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_1"], data[4])
        elif(data.size() == 6):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_1"], data[4], data[5])
        elif(data.size() == 7):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_1"], data[4], data[5], data[6])
        elif(data.size() <= 8):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_1"], data[4], data[5], data[6], data[7])

        if(data.size() == 9):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_2"], data[8])
        elif(data.size() == 10):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_2"], data[8], data[9])
        elif(data.size() == 11):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_2"], data[8], data[9], data[10])
        elif(data.size() <= 12):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_2"], data[8], data[9], data[10], data[11])

        if(data.size() == 13):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_3"], data[12])
        elif(data.size() == 14):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_3"], data[12], data[13])
        elif(data.size() == 15):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_3"], data[12], data[13], data[14])
        elif(data.size() <= 16):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_DATA_3"], data[12], data[13], data[14], data[15])

        self.transaction(
            gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_7B_MULTI"], address)
        error = self.rx.data.data3 != 0x4
        if(error):
            gbtsca_exception.GBT_SCA_I2C_Exception(
                sys._getframe().f_lineno, "i2cWrite", "gbtsca.py", self.rx.data.data3)

    def i2cRead(self, bus, address, nBytes):
        #print("i2cRead: "+bus+", "+address+", "+nBytes+"\n")

        self.transaction(
            gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["R_CTRL_REG"])
        ctrlBits = self.rx.data.data3

        self.transaction(gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_CTRL_REG"], (
            ctrlBits & ~gbtsca_constants.I2C["MASK_CTRL_REG_NBYTE"]) | (nBytes << 2))

        self.transaction(
            gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_7B_MULTI"], address)
        error = self.rx.data.data3 != 0x4
        if(error):
            gbtsca_exception.GBT_SCA_I2C_Exception(
                sys._getframe().f_lineno, "i2cRead", "gbtsca.py", self.rx.data.data3)

        reply = []

        if(nBytes > 0):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["R_DATA_0"])
            if(nBytes <= 1):
                reply.append(self.rx.data.data3)
            if(nBytes <= 2):
                reply.append(self.rx.data.data2)
            if(nBytes <= 3):
                reply.append(self.rx.data.data1)
            if(nBytes <= 4):
                reply.append(self.rx.data.data0)
        if(nBytes > 4):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["R_DATA_1"])
            if(nBytes <= 5):
                reply.append(self.rx.data.data3)
            if(nBytes <= 6):
                reply.append(self.rx.data.data2)
            if(nBytes <= 7):
                reply.append(self.rx.data.data1)
            if(nBytes <= 8):
                reply.append(self.rx.data.data0)
        if(nBytes > 8):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["R_DATA_2"])
            if(nBytes <= 9):
                reply.append(self.rx.data.data3)
            if(nBytes <= 10):
                reply.append(self.rx.data.data2)
            if(nBytes <= 11):
                reply.append(self.rx.data.data1)
            if(nBytes <= 12):
                reply.append(self.rx.data.data0)
        if(nBytes > 12):
            self.transaction(
                gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["R_DATA_3"])
            if(nBytes <= 13):
                reply.append(self.rx.data.data3)
            if(nBytes <= 14):
                reply.append(self.rx.data.data2)
            if(nBytes <= 15):
                reply.append(self.rx.data.data1)
            if(nBytes <= 16):
                reply.append(self.rx.data.data0)

        return reply

    def i2cWrite_single(self, bus, address, data):
        self.transaction(
            gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["W_7B_SINGLE"], address, data)
        error = self.rx.data.data3 != 0x4
        if(error):
            raise gbtsca_exception.GBT_SCA_I2C_Exception(
                sys._getframe().f_lineno, "i2cWrite_single", "gbtsca.py", self.rx.data.data3)

    def i2cRead_single(self, bus, address):
        self.transaction(
            gbtsca_constants.I2C["CHANNEL_MAP"][bus], gbtsca_constants.I2C["R_7B_SINGLE"], address)
        error = self.rx.data.data3 != 0x4
        if(error):
            raise gbtsca_exception.GBT_SCA_I2C_Exception(
                sys._getframe().f_lineno, "i2cRead_single", "gbtsca.py", self.rx.data.data3)
        return self.rx.data.data2

    def gpioSetDirection(self, direction):
        self.transaction(gbtsca_constants.GPIO["CHANNEL"], gbtsca_constants.GPIO["W_DIRECTION"], (0xff000000 &
                                                                                                                      direction) >> 24, (0x00ff0000 & direction) >> 16, (0x0000ff00 & direction) >> 8, (0x000000ff & direction))

    def gpioGetDirection(self):
        self.transaction(gbtsca_constants.GPIO["CHANNEL"],
                         gbtsca_constants.GPIO["R_DIRECTION"])

        return (self.rx.data.data3 << 24) | (self.rx.data.data2 << 16) | (self.rx.data.data1 << 8) | (self.rx.data.data0)

    def gpioRead(self):
        self.transaction(gbtsca_constants.GPIO["CHANNEL"],
                         gbtsca_constants.GPIO["R_DATAIN"])

        return (self.rx.data.data3 << 24) | (self.rx.data.data2 << 16) | (self.rx.data.data1 << 8) | self.rx.data.data0

    def dacWrite(self, channel, value):
        # Channel is A, B, C, or D. Value ranges from 0-1.0V, 0x00->0xFF.
        if(channel.lower() == 'a'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["W_A"], value & 0xFF, 0, 0, 0)
        elif(channel.lower() == 'b'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["W_B"], value & 0xFF, 0, 0, 0)
        elif(channel.lower() == 'c'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["W_C"], value & 0xFF, 0, 0, 0)
        elif(channel.lower() == 'd'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["W_D"], value & 0xFF, 0, 0, 0)
        return self.rx.data.data3

    def dacRead(self, channel):
        # Channel is A, B, C, or D. Return value ranges from 0x00->0xFF, corresponding to 0->1V.
        if(channel.lower() == 'a'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["R_A"],0,0,0)
        elif(channel.lower() == 'b'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["R_B"])
        elif(channel.lower() == 'c'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["R_C"])
        elif(channel.lower() == 'd'):
            self.transaction(gbtsca_constants.DAC["CHANNEL"],
                             gbtsca_constants.DAC["R_D"])
        return self.rx.data.data3

    def adcRead(self, channel):
        self.transaction(gbtsca_constants.ADC["CHANNEL"],
                         gbtsca_constants.ADC["W_MUX_REG"], 0, 0, 0, channel & 0xFF)
        #         print("Step 1 done\n");
        try:
            self.transaction(gbtsca_constants.ADC["CHANNEL"],
                             gbtsca_constants.ADC["GO_REG"], 0, 0, 0, 1)
        except (gbtsca_exception.GBT_SCA_HDLC_Exception):
            print(
                "ADC did not reply -- generally locks up the SCA, requiring a hard reset.\n")
            # throw e; # now we can throw it again..
        #     print(self.rx.data.data3+""+self.rx.data.data2+""+self.rx.data.data1+""+self.rx.data.data0)
        return (self.rx.data.data1 << 8) | (self.rx.data.data0)

    def gpioWrite(self, data, mask):
        self.masked32BitWrite(gbtsca_constants.GPIO["CHANNEL"],
                              gbtsca_constants.GPIO["R_DATAOUT"], gbtsca_constants.GPIO["W_DATAOUT"], mask, data)

    def reset(self):
        self.resethelper.reset()

    def reset_roc(self):
        self.resethelper.reset_roc()

    def softReset(self):
        pass

    def masked32BitWrite(self, channel, readCommand, writeCommand, mask, data):
        d0 = data & 0xff
        d1 = (data >> 8) & 0xff
        d2 = (data >> 16) & 0xff
        d3 = data >> 24

        m0 = mask & 0xff
        m1 = (mask >> 8) & 0xff
        m2 = (mask >> 16) & 0xff
        m3 = mask >> 24

        self.transaction(channel, readCommand)
        self.transaction(channel, writeCommand, ((~m3) & self.rx.data.data3) | (d3 & m3), ((~m2) & self.rx.data.data2) | (
            d2 & m2), ((~m1) & self.rx.data.data1) | (d1 & m1), ((~m0) & self.rx.data.data0) | (d0 & m0))

    def enableGPIO(self, enableGPIO):
        self.masked8BitWrite(gbtsca_constants.CTRL["CHANNEL_CTRL"], gbtsca_constants.CTRL["R_CRB"],
                             gbtsca_constants.CTRL["W_CRB"],
                             gbtsca_constants.CTRL["MASK_CRB_PARAL"], gbtsca_constants.CTRL["MASK_CRB_PARAL"] if enableGPIO else 0)

    def setI2CSpeed(self, i2cBus, speed):
        self.masked8BitWrite(gbtsca_constants.I2C["CHANNEL_MAP"][i2cBus], gbtsca_constants.I2C["R_CTRL_REG"],
                             gbtsca_constants.I2C["W_CTRL_REG"], gbtsca_constants.I2C["MASK_CTRL_REG_SPEED"], speed)

    def setI2CSCLMode(self, i2cBus, directDrive):
        self.masked8BitWrite(gbtsca_constants.I2C["CHANNEL_MAP"][i2cBus], gbtsca_constants.I2C["R_CTRL_REG"],
                             gbtsca_constants.I2C["W_CTRL_REG"],
                             gbtsca_constants.I2C["MASK_CTRL_REG_SCLDRIVE"], gbtsca_constants.I2C["MASK_CTRL_REG_SCLDRIVE"] if directDrive else 0)
