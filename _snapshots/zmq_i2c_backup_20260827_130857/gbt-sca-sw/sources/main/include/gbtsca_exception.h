#ifndef GBTSCA_EXCEPTION
#define GBTSCA_EXCEPTION 1

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

#include <uhal/uhal.hpp>

#include <vector>
#include <string>
#include <iostream>

using namespace uhal;

class GBT_SCA_Exception
{
protected:
    int line_;
    std::string function_;
    std::string file_;
    std::string message_;

public:
    
    GBT_SCA_Exception(const int line, const std::string& function, const std::string& file, const std::string& message) : line_(line), function_(function), file_(file), message_(message) {}

    int getLineNumber() const { return line_; }
    std::string getFunctionName() const { return function_; }
    std::string getFileName() const { return file_; }
    std::string getMessage() const { return message_; }
    virtual std::string getPrintMessage() const
    {
        return file_ + ":" + std::to_string(line_) + ", in function \"" + function_ + "\" -- " + message_;
    }

    void print() const
    {
        std::cout << getPrintMessage() << std::endl;
    }
};

#define THROW_SCA_EXCEPTION( _message ) \
    throw GBT_SCA_Exception( __LINE__, __func__, __FILE__, _message)

class GBT_SCA_I2C_Exception : public GBT_SCA_Exception
{
private:
    uint8_t errorStatus_;

public:
    GBT_SCA_I2C_Exception(const int line, const std::string& function, const std::string& file, const uint8_t status) : GBT_SCA_Exception(line, function, file, "I2C Error"), errorStatus_(status) {}

    uint8_t getStatus() const { return errorStatus_; }
    std::string getPrintMessage() const
    {
        char status[4];
        sprintf(status, "%02x", errorStatus_);
        return file_ + ":" + std::to_string(line_) + ", in function \"" + function_ + "\" -- " + message_ + " -- status code: " + status;
    }

};

#define THROW_SCA_I2C_EXCEPTION( _status ) \
    throw GBT_SCA_I2C_Exception( __LINE__, __func__, __FILE__,  _status)

class GBT_SCA_HDLC_Exception : public GBT_SCA_Exception
{
private:
    uint8_t errorStatus_;

public:
    GBT_SCA_HDLC_Exception(const int line, const std::string& function, const std::string& file, const std::string& message, const uint8_t status) : GBT_SCA_Exception(line, function, file, "HDLC Error: " + message), errorStatus_(status) {}

    uint8_t getStatus() const { return errorStatus_; }
    std::string getPrintMessage() const
    {
        char status[4];
        sprintf(status, "%02x", errorStatus_);
        return file_ + ":" + std::to_string(line_) + ", in function \"" + function_ + "\" -- " + message_ + " -- error code: " + status;
    }

};

#define THROW_SCA_HDLC_EXCEPTION( _message, _status )                    \
    throw GBT_SCA_HDLC_Exception( __LINE__, __func__, __FILE__, _message,  _status)

#endif
