import time


class data():
    def __init__(self):
        self.address = 0
        self.channel = 0
        self.transID = 0
        self.control = 0
        self.length = 0
        self.error = 0
        self.data0 = 0
        self.data1 = 0
        self.data2 = 0
        self.data3 = 0


class Rx_helper():

    def __init__(self, ipbushw, baseName):
        self.NODE_NAME = "_GBT_SCA_rx"
        self.node = ipbushw.getNode(baseName+self.NODE_NAME)
        self.clear()
        self.data = data()

    def wait_IRQ(self, timeout_ms):
        # Blocking read to wait for incoming interrupt.
        dvalid = self.node.getNode("interrupt").read()
        self.node.getClient().dispatch()

    def rxread(self):
        address = self.node.getNode("address").read()
        channel = self.node.getNode("channel").read()
        transID = self.node.getNode("transID").read()
        control = self.node.getNode("control").read()
        length = self.node.getNode("length").read()
        error = self.node.getNode("error").read()
        data0 = self.node.getNode("data0").read()
        data1 = self.node.getNode("data1").read()
        data2 = self.node.getNode("data2").read()
        data3 = self.node.getNode("data3").read()
        self.node.getClient().dispatch()
        self.data.address = address.value()
        self.data.channel = channel.value()
        self.data.transID = transID.value()
        self.data.control = control.value()
        self.data.length = length.value()
        self.data.error = error.value()
        self.data.data0 = data0.value()
        self.data.data1 = data1.value()
        self.data.data2 = data2.value()
        self.data.data3 = data3.value()

    def fetch(self, block=False, timeout=0.1):
        self.wait_IRQ(timeout)
        dvalid = self.node.getNode("rdatavalid").read()
        self.node.getClient().dispatch()
        if(dvalid.value()):
            self.rxread()
            return True

        # there is nothing to read
        return False

    def pop(self):
        dvalid = self.node.getNode("rdatavalid").read()
        self.node.getClient().dispatch()
        if(dvalid.value()):
            # there is something to read
            self.node.getNode("pop").write(1)
            self.node.getClient().dispatch()
            # rxaread()

    def clear(self):
        # flush the read fifo
        dvalid = self.node.getNode("rdatavalid").read()
        self.node.getClient().dispatch()

        while(dvalid.value()):
            self.pop()
            dvalid = self.node.getNode("rdatavalid").read()
            self.node.getClient().dispatch()

    def rxprint(self):
        print("Rx address: "+str(self.data.address))
        print("Rx transId: "+str(self.data.transID))
        print("Rx control:       "+str(self.data.control))
        if((self.data.control & 0x1) == 0):
            print("    I frame")
            print("    N(S):       "+str((self.data.control >> 1) & 0x7))
            print("    N(R):       "+str((self.data.control >> 5) & 0x7))
        else:
            if(self.data.control & 0x2):
                print("    U frame")
            else:
                print("    S frame")
                if(((self.data.control >> 2) & 0x3) == 0x0):
                    print("    receive ready")
                elif(((self.data.control >> 2) & 0x3) == 0x1):
                    print("    REJ")
                elif(((self.data.control >> 2) & 0x3) == 0x2):
                    print("    receive not ready")
                elif(((self.data.control >> 2) & 0x3) == 0x3):
                    print("    SREJ")
                print("    N(R):       "+str((self.data.control >> 5) & 0x7))
        print("Rx channel: "+str(self.data.channel))
        print("Rx error:         "+str(self.data.error))
        print("Rx length:  "+str(self.data.length))
        print("Rx data:    "+str(self.data.data3)+" "+str(self.data.data2) +
              " "+str(self.data.data1)+" "+str(self.data.data0))
