#include <errno.h>
#include <stdio.h>
#include <gbtsca_exception.h>
#include <iostream>

using namespace uhal;

std::ostream& operator<<(std::ostream& out, const GBT_SCA_Exception& e)
{
    return out << e.getPrintMessage();
}

std::ostream& operator<<(std::ostream& out, const GBT_SCA_I2C_Exception& e)
{
    return out << e.getPrintMessage();
}

std::ostream& operator<<(std::ostream& out, const GBT_SCA_HDLC_Exception& e)
{
    return out << e.getPrintMessage();
}
