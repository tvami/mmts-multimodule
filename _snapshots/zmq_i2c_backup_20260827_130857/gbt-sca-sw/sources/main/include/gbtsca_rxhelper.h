#ifndef GBTSCA_RXHELPER
#define GBTSCA_RXHELPER 1

#include <cstring>
#include <uhal/uhal.hpp>

#include <vector>
#include <string>
#include <iostream>

using namespace uhal;

class Rx_helper 
{ 
private:
  const Node& node_;
  static constexpr char* NODE_NAME = "_GBT_SCA_rx";

public:
  struct rx_data
  {
    uint8_t address;
    uint8_t control; 
    uint8_t transID; 
    uint8_t channel; 
    uint8_t length; 
    uint8_t error; 
    uint8_t data0; 
    uint8_t data1; 
    uint8_t data2; 
    uint8_t data3; 
  } data;
  
    Rx_helper(const uhal::HwInterface* ipbushw, const std::string& baseName);

    void wait_IRQ(int timeout_ms);
    void rxread();
    bool fetch(bool block = false, uint32_t timeout = 100);
    void pop();
    void clear();
    void print();

    ~Rx_helper()
    {
    }
};

#endif
