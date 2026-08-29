from nested_dict import nested_dict
from smbus2 import SMBus, i2c_msg
import time
from math import log

class ADCTrophyV2():

    def __init__(self):
        self.adc_pwr = {}
        self.adc_probeDC = {}
        self.adc_cal = {}
        i2c_labels = glob.glob("/sys/class/i2c-dev/i2c-*/device/*/of_node/label")
        for labelfile in i2c_labels:
            with open(labelfile) as fin:
                label = fin.readline()
                if label.find('adc_pwr')==0:
                    self.adc_pwr['piv_a']=labelfile.split('of_node')[0]+'in4_input'
                    self.adc_pwr['piv_d']=labelfile.split('of_node')[0]+'in5_input'
                elif label.find('adc_s0')==0:
                    self.adc_probeDC['roc_s0']=labelfile.split('of_node')[0]+'in5_input'
                    self.adc_cal['roc_s0']    =labelfile.split('of_node')[0]+'in4_input'
                elif label.find('adc_s1')==0:
                    self.adc_probeDC['roc_s1']=labelfile.split('of_node')[0]+'in5_input'
                    self.adc_cal['roc_s1']    =labelfile.split('of_node')[0]+'in4_input'
                elif label.find('adc_s2')==0:
                    self.adc_probeDC['roc_s2']=labelfile.split('of_node')[0]+'in5_input'
                    self.adc_cal['roc_s2']    =labelfile.split('of_node')[0]+'in4_input'

    def read_pwr(self):
        """ Return reading of TrophyBoard's analog (piv_a) and digital (piv_d) ADCs. """
        res = {}
        for lbl, cmd in self.adc_pwr.items():
            with open(cmd) as f:
                res[lbl] = f.read().rstrip('\n')
        return res

    def read_adc(self, cfgs):
        """
        Return reading of TrophyBoard's probeDC and InCtest ADCs.
        Since both halves of a chip and all the chips in a sector are wired together for one ADC,
        we have to set and read probeDC and calibDAC sequentially per chip and per half.
        Orientation of HexaBoard determines which ADC (in TrophyBoard sectors) have to be read.
        """
        
        pdc_adc = {'roc_s0': '/sys/class/i2c-dev/i2c-2/device/2-0048/in5_input',
                   'roc_s1': '/sys/class/i2c-dev/i2c-3/device/3-0049/in5_input',
                   'roc_s2': '/sys/class/i2c-dev/i2c-1/device/1-0048/in5_input', }

        cal_adc = {'roc_s0': '/sys/class/i2c-dev/i2c-2/device/2-0048/in4_input',
                   'roc_s1': '/sys/class/i2c-dev/i2c-3/device/3-0049/in4_input',
                   'roc_s2': '/sys/class/i2c-dev/i2c-1/device/1-0048/in4_input', }

        cfg_keys = get_all_keys(cfgs)    # scan the received cfg for 'Calib_dac' or 'Probe_dcX'
        if 'Calib' in cfg_keys: 
            adc  = self.adc_cal#cal_adc
            keys = ['IntCtest', 'ExtCtest', 'Calib']
        elif any('probe_dc' in str(key) for key in cfg_keys): 
            adc  = self.adc_probeDC#pdc_adc
            keys = [key for key in cfg_keys if 'probe_dc' in key]

        # expand original cfgs (ocfgs) and zero'd cfgs (zcfgs)
        res = nested_dict()
        print(yaml.dump(cfgs))
        ocfgs = self.translator.expand_cfgs(cfgs, self.rocs)
        zcfgs = ocfgs.copy()
        for key in keys: zcfgs = nested_update(zcfgs, key=key, value=0)
        
        # group ROCs that can be configured in parallel
        rocs = sorted(list(ocfgs.keys()), key=lambda roc: roc[-1])
        confGroup = [list(g) for _, g in groupby(rocs, key=lambda roc: roc[-1])]

        for sel_half in [0,1]:
            for group in confGroup:
                # create cfgs for ROCs and Halves that can be configured together
                ncfgs = nested_dict(zcfgs)
                for roc in group:
                    ncfgs[roc]['ReferenceVoltage'][sel_half] = ocfgs[roc]['ReferenceVoltage'][sel_half]

                # configure, readout & save
                self.configure(ncfgs.to_dict())
                for roc in group:
                    try:
                        with open(adc[roc]) as f:
                            res[roc][sel_half] = f.read().rstrip('\n')
                    except:
                        res[roc][sel_half] = 0
                        continue

        self.configure(zcfgs)   # deconfigure
        return res.to_dict()


class genericADCTrophyV3():
    """
    13 January 2023
    Authors: Margaret Helene Lockwood, Fabio Monti
    Abstract class to handle the temperature sensor and the adc chips on the trophyv3 board.
    This class provides methods for configuration and readout common to both chips.
    Reference: https://www.ti.com/lit/ds/symlink/ads112c04.pdf
    """
    
    def __init__(self, cfgs):
        # initialize bus
        self.i2c_address = cfgs["i2c_address"]
        self.bus = SMBus(cfgs["bus"])

        # initialize the four 8-bit registers
        # reg 0: MUX and gain settings
        # reg 1: voltage reference, data rate and readout mode settings 
        # reg 2: data ready bit + setup data counter, integrity check, and burn-out current +
        #        + setup excitation current sources for temperature measurements
        # reg 3: routing of excitation current sources for temperature measurements
        self.conf_registers = cfgs["conf_registers"]
        self.reconfigure_registers(self.conf_registers)
        self.initialize()

        if "gain" in cfgs:
            self.gain=cfgs["gain"]
        else:
            self.gain=1

        if "offset" in cfgs:
            self.offset=cfgs["offset"]
        else:
            self.offset=0.0

    def start_sync(self):
        """
        Start or restart conversions. Note that the first conversion starts 28.5*t_{clk} in normal mode 
        or 105*t{clk} in turbo after command is sent.
        """
        self.bus.write_byte(self.i2c_address, 0b1000)

    def reset(self):
        """Send reset command which sets all register values to 0"""
        self.bus.write_byte(self.i2c_address, 0b0110)

    def write_register(self, regidx, regval):
        """
        Configure register regidx with value regval(8 bits) and update cached values.
        """
        self.bus.write_byte_data(self.i2c_address, 0b01000000+(4*regidx), regval)
        self.conf_registers[regidx] = regval
        if regidx==1:
            self.turbo_mode = bool((self.conf_registers[1] >> 4) & 1)
            self.continuos_readout = bool((self.conf_registers[1] >> 3) & 1)
        if regidx==0:
            gain_bits = ((self.conf_registers[0] & 0b00001110) >> 1)
            print("gain_bits", gain_bits)
            self.gain = 2**gain_bits
            print("gain", self.gain)

    def reconfigure_registers(self, regvals):
        """
        Resets device and then configures registers. 
        c is an array with configuration for each registor 
        """
        self.reset()
        #print("before configuration",self.read_all())
        #print("Desired config is ",c)
        for regidx,regval in enumerate(regvals):
            self.write_register(regidx, regval)
            #print("register %s configured", i)
        #print("after configuration",self.read_all())
        #print("Registers configured")

    def initialize(self):
        if self.continuos_readout:
            self.start_sync()

    def read_register(self, r):
        """Read selected register, r. Returns register config."""
        self.bus.write_byte(self.i2c_address, 0b100000+(4*r))
        message=self.bus.read_byte(self.i2c_address)
        #print('register %s reads %s', r, message)
        return message 

    def data_ready(self):
        """checks if read only bit (bit 7) on register 2 is 0 or 1. If R bit is 1, then we are ready to read data."""
        data_ready = (self.read_register(2) >> 7) & 1
        #print("DRDY is %s", data_ready)
        return data_ready

    def wait_for_data(self):
        """Waits for new conversion. Function used in read_data during single shot conversion.
        I should double check to see if waiting for data is nessesary. I think it is.  """
        timetot=0.0
        wait=1E-6
        while not self.data_ready():
            time.sleep(wait)
            timetot+=wait
        #print("Waited %s seconds for data", timetot)

    def read_data(self):
        """
        Read data. Waits for read bit to be set to high indicating data is ready. 
        Be sure to configure the registers based on the type of data you want to read
        """
        if not self.continuos_readout:
            self.start_sync()
            #print("Entered start/sync mode.")
        self.wait_for_data()
        self.bus.write_byte(self.i2c_address, 0b00010000)
        #print("Queen asked worker for data.")
        read=i2c_msg.read(self.i2c_address, 2)
        self.bus.i2c_rdwr(read)
        conversion=list(read)
        data = conversion[0]*256+conversion[1]
        #print("Worker sent data. The data is %s", conversion[0]*256+conversion[1])
        return data
    
    def binary2voltage(self, bin_data):
        conversion = 2.048 / self.gain / 32768 
        if (bin_data & (1 << (16 - 1))) != 0:
            bin_data = bin_data - (1 << 16)
        return conversion*bin_data-self.offset


class ADC1TrophyV3(genericADCTrophyV3):
    """
    13 January 2023
    Authors: Margaret Helene Lockwood, Fabio Monti
    Interface to configure and readout the ADC chip (ADS112C04) on the trophy v3 boards 
    """

    def __init__(self, cfgs):
        super().__init__(cfgs)
        # register 0 configurations to read the voltage on the i-th input line wrt GND
        self.probe_map = {
            1: (0b10010000+int(2*log(self.gain,2))), #probe_DC1
            2: (0b10100000+int(2*log(self.gain,2))), #probe_DC2
            3: (0b10110000+int(2*log(self.gain,2))), #probe_DC3
            4: (0b10000000+int(2*log(self.gain,2))), #probe_LVS
            #5: 0b01100010, #probe_DC2-probe_DC3 
            #6: 0b01110010, #probe_DC3-probe_DC2
            #7: 0b01100000,
            #8: 0b01110000
        }

    def read_pwr(self):
        pass

    def probe_DC(self, input_line: int):
        """
        Probe given input line and return the data in binary format.
        The input lines are defined in self.probe_map.keys() 
        """
        self.write_register(0, self.probe_map[input_line]) #update mux settings
        data = self.read_data()
        return data

    def read_adc(self, cfgs):
        res = nested_dict()
        for i in self.probe_map.keys():
            data = self.probe_DC(i)
            res[i] = self.binary2voltage(data)
        return res.to_dict()

    def meas_adc_offset(self,cfgs,N=100):
        self.offset = 0
        average=0
        for i in range(N):
            self.write_register(0, (0b11100000+int(2*log(self.gain,2)))) #update mux settings
            data = self.read_data()
            average += self.binary2voltage(data)
        average /= N
        offset = average
        self.offset = offset
        print('ADC offset: ',offset)
        return offset

    
class RTD_TrophyV3(genericADCTrophyV3):
    """
    11 May 2023
    Authors: Greg Powers, Fabio Monti
    Read temperature dadta on the trophy v3 boards 
    """
    def __init__(self, cfgs):
        super().__init__(cfgs)

    def flip_bits(self, bit):
        """turns 0 to 1 and 1 to 0"""
        bits = bit[2:]
        flip_bits = '' 
        for i in bits:
            if i == '0':
                flip_bits += '1'
            else:
                flip_bits += '0'
        print(flip_bits)
        return flip_bits 

    def twos_complement(self, number): 
        """input a datum, return the 2s complement for reading voltages"""
        minused=number-0b1                              
        flipped=self.flip_bits(bin(minused))     
        return int(flipped,2)

    def meas_adc_temp(self,cfgs):
        self.write_register(1,0b00000001)
        #>>2 to left-shift the bits by 2 (only want 1st 14)
        bin_temp = self.read_data()>>2
        #bin_temp = 0b11110011100000
        print(bin_temp)
        if bin_temp <= 0b01111111111111:
            temperature = bin_temp*.03125
        else:
            temperature = -1*self.twos_complement(bin_temp)*.03125
        return temperature

    def meas_rtd_temp(self,cfgs):
        self.gain = 2
        self.write_register(0,0b00000010) 
        self.write_register(1,0b00001000)
        self.write_register(2,0b00000101)
        self.write_register(3,0b10000000)

        data = self.read_data()
        I = 500e-6
        V = self.binary2voltage(data)
        R = V/I
        T = round((R-1000)/(1000*0.00391), 1)

        self.write_register(2,0b00000000)
        return T