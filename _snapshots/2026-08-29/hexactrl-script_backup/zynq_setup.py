import paramiko
from time import sleep
import util
import logging

class zynq_setup:
    def __init__(self,ip,username,password):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(ip, username=username, password=password)
        self.logger = logging.getLogger('ZYNQ')
        util.setLoggingLevel('INFO','ZYNQ')

    def load(self,fwname):
        stdin, stdout, stderr = self.ssh_client.exec_command(f'fw-loader load {fwname}')
        self.logger.info( f'Error while loading FPGA: {stderr.readlines()}' )
        stream=''
        for line in stdout.readlines():
            stream+=line
        self.logger.info( f'Loading FPGA: \n{stream}' )
        sleep(1.0)
        
    def start_software_servers(self):
        self.ssh_client.exec_command("systemctl restart i2c-server")
        self.ssh_client.exec_command("systemctl restart daq-server")
        self.logger.info("daq-server and i2c-server started")

    def close(self):
        self.ssh_client.exec_command("systemctl stop i2c-server")
        self.ssh_client.exec_command("systemctl stop daq-server")
        self.ssh_client.close()
        self.logger.info("daq-server and i2c-server stopped")

import argparse
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--hexaIP",
                        action="store", dest="hexaIP",
                        help="IP address of the zynq on the hexactrl board")
    args = parser.parse_args()
    z = zynq_setup(args.hexaIP,'root','centos')
    z.load('hexaboard-hd-tester-v1p1-trophy-v3')
    z.start_software_servers()
    z.close()
