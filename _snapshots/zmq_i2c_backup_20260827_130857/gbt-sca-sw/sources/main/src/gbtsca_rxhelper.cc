#include <gbtsca_rxhelper.h>

#include <stdint.h>
#include <stdlib.h>
#include <cstring>
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <sys/mman.h>
#include <vector>
#include <string>
#include <iostream>

using namespace uhal;

Rx_helper::Rx_helper(const uhal::HwInterface* ipbushw, const std::string& baseName) : node_(ipbushw->getNode(baseName+Rx_helper::NODE_NAME)) { 
  clear();
}

void Rx_helper::wait_IRQ(int timeout_ms)
{
    ValWord < uint32_t >  dvalid = node_.getNode("interrupt").read();
    node_.getClient().dispatch();
}

void Rx_helper::rxread()
{
   ValWord < uint32_t >  address=node_.getNode("address").read();
   ValWord < uint32_t >  channel=node_.getNode("channel").read();
   ValWord < uint32_t >  transID=node_.getNode("transID").read();
   ValWord < uint32_t >  control=node_.getNode("control").read();
   ValWord < uint32_t >  length=node_.getNode("length").read();
   ValWord < uint32_t >  error=node_.getNode("error").read();
   ValWord < uint32_t >  data0=node_.getNode("data0").read();
   ValWord < uint32_t >  data1=node_.getNode("data1").read();
   ValWord < uint32_t >  data2=node_.getNode("data2").read();
   ValWord < uint32_t >  data3=node_.getNode("data3").read(); 
   node_.getClient().dispatch();
   data.address=address.value();
   data.channel=channel.value();
   data.transID=transID.value();
   data.control=control.value();
   data.length=length.value();
   data.error=error.value();
   data.data0=data0.value();
   data.data1=data1.value();
   data.data2=data2.value();
   data.data3=data3.value();
}

bool Rx_helper::fetch(bool block, uint32_t timeout)
{
    wait_IRQ(timeout);
    ValWord < uint32_t >  dvalid = node_.getNode("rdatavalid").read();
    node_.getClient().dispatch();
    if(dvalid.value())
    {
        rxread();
        return true;
    } 

    //there is nothing to read
    return false;
}

void Rx_helper::pop()
{
    ValWord < uint32_t >  dvalid = node_.getNode("rdatavalid").read();
    node_.getClient().dispatch();
    if(dvalid.value())
    {
        //there is something to read
        node_.getNode("pop").write(1);
        node_.getClient().dispatch();
      //rxaread();
    }
}

void Rx_helper::clear()
{
    //flush the read fifo
    ValWord < uint32_t >  dvalid = node_.getNode("rdatavalid").read();
    node_.getClient().dispatch();
   
    while(dvalid.value())
    {
        pop();
        dvalid = node_.getNode("rdatavalid").read();
        node_.getClient().dispatch(); 
    }
}

void Rx_helper::print()
{
    printf("Rx address: %8x\n", data.address);
    printf("Rx transId: %8x\n", data.transID);
    printf("Rx control:       %02x\n", data.control);
    if((data.control & 0x1) == 0)
    {
        printf("    I frame\n");
        printf("    N(S):       %02d\n", (data.control >> 1 ) & 0x7);
        printf("    N(R):       %02d\n", (data.control >> 5 ) & 0x7);
    }
    else
    {
        if(data.control & 0x2)
        {
            printf("    U frame\n");
        }
        else
        {
            printf("    S frame\n");
            if     (((data.control >> 2 ) & 0x3) == 0x0) printf("    receive ready\n");
            else if(((data.control >> 2 ) & 0x3) == 0x1) printf("    REJ\n");
            else if(((data.control >> 2 ) & 0x3) == 0x2) printf("    receive not ready\n");
            else if(((data.control >> 2 ) & 0x3) == 0x3) printf("    SREJ\n");
            printf("    N(R):       %02d\n", (data.control >> 5 ) & 0x7);
        }
    }
    printf("Rx channel: %8x\n", data.channel);
    printf("Rx error:         %02x\n", data.error);
    printf("Rx length:  %8x\n", data.length);
    printf("Rx data:    %02x%02x%02x%02x\n", data.data3, data.data2, data.data1, data.data0);	
}
