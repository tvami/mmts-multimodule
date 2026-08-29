import time
import serial

from pymeasure.adapters import Adapter, SerialAdapter, VISAAdapter

class PrologixEthernetAdapter(Adapter):

    PORT = 1234

    def __init__(self, resource, address=None, rw_delay=None, auto=0, eoi=1, eos=3, **kwargs):
        """
        :param resource: A string representing the IP address of the prologix adapter
        :param address: Integer GPIB address of the desired instrument
        :param rw_delay: An optional delay to set between a write and read call for slow to respond instruments.
        :param auto: Default to 0 to turn off read-after-write and address instrument to listen
        :param eoi: Default to 0 to disable EOI assertion
        :param eos: Default to 0 to append CR+LF to instrument commands
        :param kwargs:
        """
        if isinstance(resource, VISAAdapter):
            self.resource = resource
            # print(self.resource.connection.resource_name)
            self.ip = self.resource.connection.resource_name.split('::')[1]
        else:
            self.resource = VISAAdapter('TCPIP::{}::{}::SOCKET'.format(resource, self.PORT),
                                       read_termination='\n',
                                       write_termination='\n', timeout=10000)
            self.ip = resource

        self.connection = self.resource.connection
        self.address = address
        self.rw_delay = rw_delay
        self.auto = auto
        self.eoi = eoi  # set to list to End-of-Instruction in read. (Some instruments require
        self.eos = eos  # set two terminating characters.

    def reset(self):
        """
        This command performs a power-on reset of the controller. The process takes about 5
        seconds. All input received over the network during this time are ignored and the connection is closed.
        """
        self.resource.write('++rst')

    @property
    def auto(self):
        """
        Prologix GPIB-ETHERNET controller can be configured to automatically address
        instruments to talk after sending them a command in order to read their response. The
        feature called, Read-After-Write, saves the user from having to issue read commands
        repeatedly. This property enabled or disabled the Read-After-Write feature.
        """
        self.resource.write("++auto")
        return int(self.resource.read())

    @auto.setter
    def auto(self, value):
        self.resource.write("++auto {}".format(value))

    @property
    def eoi(self):
        """
        This property enables or disables the assertion of the EOI signal with the last character
        of any command sent over GPIB port. Some instruments require EOI signal to be
        asserted in order to properly detect the end of a command.
        """
        self.resource.write("++eoi")
        return int(self.resource.read())

    @eoi.setter
    def eoi(self, value):
        self.resource.write("++eoi {}".format(value))

    @property
    def eos(self):
        """
        This command specifies GPIB termination characters. When data from host is received
        over the network, all non-escaped LF, CR and ESC characters are removed and GPIB
        terminators, as specified by this command, are appended before sending the data to
        instruments. This command does not affect data from instruments received over GPIB
        port.
        """
        self.resource.write("++eos")
        return int(self.resource.read())

    @eos.setter
    def eos(self, value):
        self.resource.write("++eos {}".format(value))

    @property
    def version(self):
        """
        Returns the version string of the Prologix controller
        """
        self.resource.write('++ver')
        return self.resource.read()

    def ask(self, command):
        """ Ask the Prologix controller, include a forced delay for some instruments.
        :param command: SCPI command string to be sent to instrument
        """

        self.write(command)
        if self.rw_delay is not None:
            time.sleep(self.rw_delay)
        return self.read()

    def write(self, command):
        """ Writes the command to the GPIB address stored in the
        :attr:`.address`
        :param command: SCPI command string to be sent to the instrument.
        """
        if self.address is not None:
            address_command = "++addr %d" % self.address
            self.resource.write(address_command)
        self.resource.write(command)

    def read(self):
        """ Reads the response of the instrument until timeout.
        :return: String ASCII response of the instrument.
        """
        self.write("++read")
        return self.resource.read()

    def gpib(self, address, rw_delay=None):
        """ Returns and PrologixEthernetAdatper object that references the GPIB
        address specified, while sharing the visa socket connection with other
        calls of this function
        :param address: Integer GPIB address of the desired instrument
        :param rw_delay: Set a custom Read/Write delay for the instrument
        :returns: PrologixEthernetAdatper for specific GPIB address
        """
        rw_delay = rw_delay or self.rw_delay
        return PrologixEthernetAdapter(self.resource, address, rw_delay=rw_delay)

    def __repr__(self):
        if self.address is not None:
            return "<PrologixEthernetAdatper(resource={}, address={})>".format(
                self.ip, self.address)
        else:
            return "<PrologixEthernetAdatper(resource={})>".format(self.ip)
