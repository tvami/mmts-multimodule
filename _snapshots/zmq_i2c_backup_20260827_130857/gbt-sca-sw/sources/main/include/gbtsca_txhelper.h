#ifndef GBTSCA_TXHELPER
#define GBTSCA_TXHELPER 1

#include <stdint.h>
#include <uhal/uhal.hpp>
#include <string>

using namespace uhal;

class Tx_helper
{ 
private:
    uint8_t nextTransId_;
    static constexpr char* NODE_NAME = "_GBT_SCA_tx";
    const Node& node_;

public:
    struct tx_data
    {
	uint8_t address; //always 0 for GBT-SCA
	uint8_t transID; 
	uint8_t channel; 
	uint8_t length; //unused?
	uint8_t command; 
	uint8_t data0; 
	uint8_t data1; 
	uint8_t data2; 
	uint8_t data3; 
    } data;

    Tx_helper(const uhal::HwInterface* ipbushw, const std::string& baseName);

    ~Tx_helper()
    {	
    }

    uint8_t push(bool sendFifo = false, uint8_t transID = 0);
    void send();
    void softReset();
    void print();
    void clear();
}; 

#endif
