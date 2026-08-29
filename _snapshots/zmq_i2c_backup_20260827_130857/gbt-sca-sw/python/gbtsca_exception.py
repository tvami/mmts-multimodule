
class GBT_SCA_Exception(Exception):
    def __init__(self, line, function, filename, message):
        self.line = line
        self.function = function
        self.fname = filename
        self.message = message

    def getLineNumber(self):
        return self.line

    def getFunctionName(self):
        return self.function

    def getFileName(self):
        return self.fname

    def getMessage(self):
        return self.message

    def getPrintMessage(self):
        return f'{self.fname}:{self.line}, in function \"{self.function}\" --  {self.message}'

    def printError(self):
        print(self.getPrintMessage())


class GBT_SCA_I2C_Exception(GBT_SCA_Exception):
    def __init__(self, line, function, fname, status):
        GBT_SCA_Exception.__init__(self, line, function, fname, "I2C Error")
        self.status = status

    def getStatus(self):
        return self.status

    def getPrintMessage(self):
        return str(self.fname) + ":" + str(self.line) + ", in function \"" + self.function + "\" -- " + self.message + " -- status code: " + str(self.status)


class GBT_SCA_HDLC_Exception(GBT_SCA_Exception):
    def __init__(self, line, function, filename, message, status):
        GBT_SCA_Exception.__init__(
            self, line, function, filename, "HDLC Error: "+message)
        self.status = status

    def getStatus(self):
        return self.status

    def getPrintMessage(self):
        return self.fname + ":" + str(self.line) + ", in function \"" + self.function + "\" -- " + self.message + " -- error code: " + self.status
