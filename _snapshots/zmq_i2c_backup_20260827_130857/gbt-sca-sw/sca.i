#define GBTSCA_MAIN

// sca.i - SWIG interface
%module sca
%{
#include "gbtsca.h"
#include "gbtsca_exception.h"
static PyObject* pException;
static PyObject* pI2CException;
static PyObject* pHDLCException;
%}

%include "stdint.i"
%include "gbtsca.h"
%include "std_string.i"
%include "std_vector.i"
%include "exception.i"

%init %{
  pException = PyErr_NewException("_sca.GBT_SCA_Exception", NULL, NULL);
  pI2CException = PyErr_NewException("_sca.GBT_SCA_I2C_Exception", NULL, NULL);
  pHDLCException = PyErr_NewException("_sca.GBT_SCA_HDLC_Exception", NULL, NULL);
  Py_INCREF(pException);
  Py_INCREF(pI2CException);
  Py_INCREF(pHDLCException);
  PyModule_AddObject(m, "GBT_SCA_Exception", pException);
  PyModule_AddObject(m, "GBT_SCA_I2C_Exception", pI2CException);
  PyModule_AddObject(m, "GBT_SCA_HDLC_Exception", pHDLCException);
%}

%exception {
   try {
      $action
   }  catch (GBT_SCA_HDLC_Exception &e) {
      PyErr_SetString(pHDLCException, e.getPrintMessage().c_str());
      SWIG_fail;
   }  catch (GBT_SCA_I2C_Exception &e) {
      PyErr_SetString(pI2CException, e.getPrintMessage().c_str());
      SWIG_fail;
   }  catch (GBT_SCA_Exception &e) {
      PyErr_SetString(pException, e.getPrintMessage().c_str());
      SWIG_fail;
   }
} 

%template(ByteVector) std::vector<uint8_t>;

%pythoncode %{
   GBT_SCA_Exception = _sca.GBT_SCA_Exception
   GBT_SCA_HDLC_Exception = _sca.GBT_SCA_HDLC_Exception
   GBT_SCA_I2C_Exception = _sca.GBT_SCA_I2C_Exception
%}

class GBT_SCA {
public: 
    GBT_SCA(const std::string& confile, const std::string& device, const std::string& basenode);
   void reset();
   void softReset();
   void transaction(const uint8_t& channel, const uint8_t& command, const uint8_t& data3 = 0, const uint8_t& data2 = 0, const uint8_t& data1 = 0, const uint8_t& data0 = 0, bool print = false);
   void masked8BitWrite(const uint8_t channel, const uint8_t readCommand, const uint8_t writeCommand, const uint8_t mask, const uint8_t data);
   void enableAdc(const bool enableADC);
   void enableI2C(const uint16_t enableI2Cs);
   uint32_t readDeviceID(bool v2 = false);
   void i2cWrite(const uint8_t& bus, const uint8_t& address, const std::vector<uint8_t>& data );
   std::vector<uint8_t> i2cRead(const uint8_t& bus, const uint8_t& address, const uint8_t& nBytes );
   void i2cWrite_single(const uint8_t& bus, const uint8_t& address, const uint8_t& data );
   uint8_t i2cRead_single(const uint8_t& bus, const uint8_t& address);
   void gpioSetDirection(const uint32_t& direction);
   uint32_t gpioGetDirection();
   uint32_t gpioRead();
   uint16_t adcRead(int channel);
   uint8_t dacRead(const char channel);
   uint8_t dacWrite(const char channel, const uint8_t value);
   void gpioWrite(const uint32_t& data, const uint32_t& mask);
   void masked32BitWrite(const uint8_t channel, const uint8_t readCommand, const uint8_t writeCommand, const uint32_t mask, const uint32_t data);
   void enableGPIO(const bool enableGPIO);
   void setI2CSpeed(const uint8_t i2cBus, const uint8_t speed);
   void setI2CSCLMode(const uint8_t i2cBus, const bool directDrive);
};   
   
