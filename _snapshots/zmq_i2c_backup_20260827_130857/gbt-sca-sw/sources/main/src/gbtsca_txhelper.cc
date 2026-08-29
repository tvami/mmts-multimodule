#include <stdint.h>
#include <stdlib.h>
#include <cstring>
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>

#include <uhal/uhal.hpp>
#include <gbtsca_txhelper.h>

#include <vector>
#include <string>
#include <iostream>

using namespace uhal;

Tx_helper::Tx_helper(const uhal::HwInterface* ipbushw, const std::string& baseName) : node_(ipbushw->getNode(baseName+NODE_NAME)) {
    clear();
}

uint8_t Tx_helper::push(bool sendFifo, uint8_t transID)
{
    uint8_t transmittedTransID = 0;

    if(transID == 0 || transID == 255) // illegal values so we use these to indicate to auto set ID
    {
        data.transID = nextTransId_;
        transmittedTransID = nextTransId_;
        if(nextTransId_ >= 254) nextTransId_ = 1;
        else                    ++nextTransId_;
    }
    else
    {
        data.transID = transID;
        transmittedTransID = transID;
    }
  
    node_.getNode("address").write(data.address);
    node_.getNode("transID").write(data.transID);
    node_.getNode("channel").write(data.channel);
    node_.getNode("length").write(data.length);
    node_.getNode("command").write(data.command);
    node_.getNode("data0").write(data.data0);
    node_.getNode("data1").write(data.data1);
    node_.getNode("data2").write(data.data2);
    node_.getNode("data3").write(data.data3);

    node_.getClient().dispatch();
    if(sendFifo)
    {
        node_.getNode("fifo_fill").write(1);
        node_.getNode("fifo_go").write(1);
    }
    else
    {
        node_.getNode("fifo_fill").write(1);
    }
    node_.getClient().dispatch();

    return transmittedTransID;
}

void Tx_helper::send()
{
    node_.getNode("fifo_go").write(1);
    node_.getClient().dispatch();
    usleep(100);
    node_.getNode("fifo_fill").write(0);
    node_.getClient().dispatch();
}

void Tx_helper::softReset()
{
    node_.getNode("fifo_go").write(4);
    node_.getClient().dispatch();
    usleep(10);
    node_.getNode("fifo_go").write(0);
    node_.getClient().dispatch();
}


void Tx_helper::print()
{
    printf("Tx address: %8x\n", data.address);
    printf("Tx transId: %8x\n", data.transID);
    printf("Tx channel: %8x\n", data.channel);
    printf("Tx command:       %02x\n", data.command);
    printf("Tx length:  %8x\n", data.length);
    printf("Tx data:    %02x%02x%02x%02x\n", data.data3, data.data2, data.data1, data.data0);	
}

void Tx_helper::clear()
{
    nextTransId_ = 2;
    data.address = 0;
    data.transID = 1; 
    data.channel = 0; 
    data.length = 0; 
    data.command = 0; 
    data.data3 = 0; 
    data.data2 = 0; 
    data.data1 = 0; 
    data.data0 = 0; 
}
