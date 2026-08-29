"""Handles storing and sending messages for the gbtsca"""
import time


class tx_data:
    def __init__(self):
        self.address = 0
        self.transID = 1
        self.channel = 0
        self.length = 0
        self.command = 0
        self.data0 = 0
        self.data1 = 0
        self.data2 = 0
        self.data3 = 0


class Tx_helper:
    def __init__(self, ipbushw, baseName):
        self.NODE_NAME = "_GBT_SCA_tx"
        self.node = ipbushw.getNode(baseName+self.NODE_NAME)
        self.data = tx_data()
        self.clear()
        self.nextTransId = 2

    def push(self, sendFifo=False, transID=0):
        transmittedTransID = 0

        # 0 and 255 illegal transaction IDs, used to indicate auto set ID.
        if(transID == 0 or transID == 255):
            self.data.transID = self.nextTransId
            transmittedTransID = self.nextTransId
            if self.nextTransId >= 254:
                self.nextTransId = 1
            else:
                self.nextTransId = self.nextTransId+1
        else:
            self.data.transID = transID
            transmittedTransID = transID

        self.node.getNode("address").write(self.data.address)
        self.node.getNode("transID").write(self.data.transID)
        self.node.getNode("channel").write(self.data.channel)
        self.node.getNode("length").write(self.data.length)
        self.node.getNode("command").write(self.data.command)
        self.node.getNode("data0").write(self.data.data0)
        self.node.getNode("data1").write(self.data.data1)
        self.node.getNode("data2").write(self.data.data2)
        self.node.getNode("data3").write(self.data.data3)

        self.node.getClient().dispatch()
        if sendFifo:
            self.node.getNode("fifo_fill").write(1)
            self.node.getNode("fifo_go").write(1)
        else:
            self.node.getNode("fifo_fill").write(1)
        self.node.getClient().dispatch()

        return transmittedTransID

    def send(self):
        self.node.getNode("fifo_go").write(1)
        self.node.getClient().dispatch()
        time.sleep(0.1)
        self.node.getNode("fifo_fill").write(0)
        self.node.getClient().dispatch()

    def softReset(self):
        self.node.getNode("fifo_go").write(4)
        self.node.getClient().dispatch()
        time.sleep(0.01)
        self.node.getNode("fifo_go").write(0)
        self.node.getClient().dispatch()

    def txprint(self):
        print("Tx address: "+self.data.address)
        print("Tx transId: "+self.data.transID)
        print("Tx channel: "+self.data.channel)
        print("Tx command:       "+self.data.command)
        print("Tx length:  "+self.data.length)
        print("Tx data:    "+self.data.data3+" "+self.data.data2 +
              " "+self.data.data1+" "+self.data.data0)

    def clear(self):
        self.nextTransId_ = 2
        self.data.address = 0
        self.data.transID = 1
        self.data.channel = 0
        self.data.length = 0
        self.data.command = 0
        self.data.data3 = 0
        self.data.data2 = 0
        self.data.data1 = 0
        self.data.data0 = 0
