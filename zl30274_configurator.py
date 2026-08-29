import smbus
import time
import sys

zl30274addr = 0x71

def ZL30274_write(i2cbus,dev_addr, memaddr, data):
    page = memaddr>>7 
    offset = memaddr & 0x7F
    i2cbus.write_byte_data(dev_addr,0x7f,page)
    i2cbus.write_byte_data(dev_addr,offset,data)
   

def ZL30274_read(i2cbus,dev_addr, memaddr):
    page = memaddr>>7 
    offset = memaddr & 0x7F
    i2cbus.write_byte_data(dev_addr,0x7f,page)      # set page
    data = i2cbus.read_byte_data(dev_addr,offset)   # set register in the page
    return data

def parseExecute(i2cbus,dev_addr,command):
    if command == "\r\n" or command == "\n":
        # empty line
        return
    
    if command.startswith(";"):
        # comment line
        return
    args = command.rsplit(',')
    action = args[0].strip()
    if action == 'X':
        reg_addr = int(args[1].strip(),16)
        reg_value = int(args[2].rsplit(';')[0].strip(),16)
        print("0x%04X,0x%02X"%(reg_addr,reg_value))
        ZL30274_write(i2cbus,dev_addr, reg_addr, reg_value)
    elif action == 'W':
        time_us = int(args[1].strip());
        print("sleeping %4.2f ms"%(time_us/1e3))
        time.sleep(time_us/1e6)
    else:
        # unknown command
        pass
    
def main():
    print("------------ ZL30274 Configurator ------------------")
    ib = smbus.SMBus(0)
    if(len(sys.argv) > 1):
        try:
            ib.write_byte(0x70,0x1)
            config_file = open(sys.argv[1], 'r')
            print("Reading configuration from file :'%s'"%(sys.argv[1]))
            for command in config_file:
                parseExecute(ib,zl30274addr,command)
        except IOError:
            print("No such file :'%s'"%(sys.argv[1]))
        finally:
            ib.write_byte(0x70,0x0)
    else:
        print("No file selected...")
   
if __name__ == "__main__":
    main()
