class generic_iic:
    def write_byte(self, address, val):
        self.write(address, [val])

    def read_byte(self, address):
        aval = self.read(address, 1)
        return aval[0]

    def write(self, address, vals):
        print("Not defined in base class!")

    def read(self, address, thelen):
        print("Not defined in base class!")
        return [-1]
