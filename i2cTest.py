from smbus2 import SMBus, i2c_msg
import time
import sys

def main():
    with SMBus(2) as bus:
        msg = i2c_msg.write(0x71, [0])
        bus.i2c_rdwr(msg)
        print(msg.buf)
   
if __name__ == "__main__":
    main()
