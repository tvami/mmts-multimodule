#ifndef GBTSCA_RESET
#define GBTSCA_RESET 1

#include <unistd.h>
#include <stdint.h>
#include <uhal/uhal.hpp>
#include <string>

using namespace uhal;

class Reset_helper 
{
private:
    const std::string name_;
    static constexpr char* NODE_NAME="_axi_gpio_0";

public:
    Reset_helper(const std::string& baseName) : name_(baseName+NODE_NAME)
    {
        
    }

    ~Reset_helper()
    {
    }
    
    void reset()
    {
    }

    void operator()()
    {
	reset();
    }
};
#endif
