import os,time,yaml,datetime
from time import sleep
from plx_gpib_ethernet import PrologixGPIBEthernet


class agilent_ctrl:
    def __init__(self,ip,address):
        self.gpib = PrologixGPIBEthernet(ip)
        while 1:
            try:
                self.gpib.connect()
                print("Connection to %s success"%(ip))
                break
            except:
                print("Fail to connect to prologix gpib controller %s; will try again in 1 sec"%(ip))
                sleep(1)
                continue
        self.gpib.select(address)

    def setV(self,chan="P6V",volt=3.3,current=1.0):
        self.gpib.write("APPL %s, %f, %f"%(chan,volt,current) )

    def on(self):
        if int(self.gpib.query("OUTP:STAT?"))==0:
            self.gpib.write("OUTP:STAT ON")
        
    def off(self):
        if int(self.gpib.query("OUTP:STAT?"))==1:
            self.gpib.write("OUTP:STAT OFF")
            self.gpib.write("SYST BEEP")

    def meas(self,dut,odir):        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        testName = "power"
        odir = "%s/%s/power/%s/"%( os.path.realpath(odir), dut, timestamp )
        os.makedirs(odir)
        volt6p=float(self.gpib.query("MEAS:VOLT? P6V"))
        current6p=float(self.gpib.query("MEAS:CURR? P6V"))
        volt25p=float(self.gpib.query("MEAS:VOLT? P25V"))
        current25p=float(self.gpib.query("MEAS:CURR? P25V"))
        volt25n=float(self.gpib.query("MEAS:VOLT? N25V"))
        current25n=float(self.gpib.query("MEAS:CURR? N25V"))

        pdir = {}
        pdir["P6V"] =  { "volt": volt6p,  "current" : current6p,  "power" : volt6p*current6p }
        pdir["P25V"] = { "volt": volt25p, "current" : current25p, "power" : volt25p*current25p }
        pdir["N25V"] = { "volt": volt25n, "current" : current25n, "power" : volt25n*current25n }
        with open(odir + "/power.yaml", 'w') as fout:
            yaml.dump(pdir, fout)
        # print(yaml.dump(pdir))

    def display(self,chan):
        self.gpib.write("INST:SEL %s"%chan)

    def close(self):
        self.gpib.close()

##
## example:
## python3 agilent_ctrl.py -d testagilent -i 128.141.89.204 -a 6
## This example mainly aims to test the script. For real use, agilent_ctrl.py should be imported as a module
##
if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    
    parser.add_option("-d", "--dut", dest="dut",
                      help="device under test")
    
    parser.add_option("-i", "--prologixIP",
                      action="store", dest="prologixIP",
                      help="IP address of the prologix gpib etherner controller")
    
    parser.add_option("-a", "--address",
                      action="store", dest="address",
                      help="gpib address set on the agilent PSU")

    parser.add_option("-o", "--odir",
                      action="store", dest="odir",default='./data',
                      help="output base directory")
    
    
    (options, args) = parser.parse_args()
    print(options)
    
    ctrler = agilent_ctrl(options.prologixIP,options.address)
    ctrler.setV("P6V",3.3,1.6)
    ctrler.setV("P25V",12,1.)
    ctrler.setV("N25V",-9,1.)
    ctrler.on()
    ctrler.display("P6V")
    sleep(2)
    ctrler.meas(options.dut,options.odir)
    ctrler.display("P6V")
    sleep(2)
    ctrler.off()
    ctrler.close()
    
