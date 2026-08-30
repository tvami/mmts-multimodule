from smbus2 import SMBus, i2c_msg
import logging
from typing import Union
from warnings import warn


class Xil_i2c:
    """
    i2c bus, effectively a fancy wrapper around the SMBus2 module
    that adds logging and a unified interface used across other
    forms of transport
    """

    def __init__(self, bus_id):
        """
        Store the bus id and initialize the smbus.

        :param bus_id: Bus id to start the SMBus module with, occupies the
            hardware by opening the corresponding file
        """
        self.bus_id = bus_id
        self.bus = SMBus()
        self.bus.open(self.bus_id)
        self.transaction_logger = logging.getLogger(f"Xil_i2c_bus_{bus_id}")
        self.transaction_logger.debug("Initializing bus")

    def write(
        self,
        address,
        data: Union[int, bytearray],
        internal_address: bytearray = None,
        log: bool = True,
    ):
        """
        Write data to the i2c peripheral specified by the address

        :param address: The address of the peripheral on the bus to write
            data to, must be 0-127
        :type address: byte
        :param data: The data to be sent to the peripheral. If an `int` is
            passed a single transaction is perfomed, if a `bytearray` is
            passed then the entire data is written as a single i2c transaction
            (aka frames)
        :type data: int, bytearray
        """
        if internal_address is not None:
            to_send = internal_address
            if data is not None:
                to_send = to_send + data
                msg_send = i2c_msg.write(address, to_send)
                self.bus.i2c_rdwr(msg_send)
            else:
                msg_send = i2c_msg.write(address, to_send)
                self.bus.i2c_rdwr(msg_send)
            if log:
                self.transaction_logger.debug(
                    f"Performing a rdwr, writing {to_send} " f"to i2c addr = {address}"
                )
            return

        if isinstance(data, int):
            self.transaction_logger.debug(
                f"Write SingleByte addr = {address}" f" data = {data:x}"
            )
            try:
                self.bus.write_byte(address, data)
            except IOError as e:
                self.transaction_logger.error(
                    "Error occurred during write: ", exc_info=True
                )
                raise IOError(e.args[0])
        else:
            if len(data) > 16:
                warn("large bulk i2c transactions are discouraged")
            self.transaction_logger.debug(
                f"Write MultiByte addr = {address}" f" data = {bytes(data).hex()}"
            )
            try:
                self.bus.write_i2c_block_data(address, 0, data)
            except IOError as e:
                self.transaction_logger.error(
                    "Error occurred during write: ", exc_info=True
                )
                raise IOError(e.args[0])

    def read(
        self,
        address: int,
        count: int = 1,
        log: bool = True,
    ):
        """
        Read data from the i2c address specified

        :param address: The address of the peripheral on the bus to read data
            from, must be 0-127
        :type address: byte
        :param count: The number of bytes to read form the bus if the count is
            larger than one a block read is performed. Defaults to 1.
        :type count: int, optional
        :return: Array of values read for the different bytes as list of ints
        :rtype: list
        """
        if count == 1:
            if log:
                self.transaction_logger.debug(
                    f"Reading SingleByte " f"from addr = {address}"
                )
            try:
                ret = self.bus.read_byte(address).to_bytes(1, "little")
            except IOError as e:
                self.transaction_logger.error(
                    "Error occurred during read: ", exc_info=True
                )
                raise IOError(e.args[0])
            if log:
                self.transaction_logger.debug(f"Read returned {ret}")
        else:
            if log:
                self.transaction_logger.debug(
                    f"Reading {count} Bytes " f"from addr = {address}"
                )
            try:
                read = i2c_msg.read(address, count)
                self.bus.i2c_rdwr(read)
                ret = bytearray(list(read))
            except IOError as e:
                self.transaction_logger.error(
                    "Error occurred during read: ", exc_info=True
                )
                raise IOError(e.args[0])
            if log:
                self.transaction_logger.debug(f"Read returned {ret.hex()}")
        return ret

    def __del__(self):
        self.transaction_logger.debug("Closing bus")
        self.bus.close()

    def scan(self):
        """
        Attempt to read from every address on the bus and collect all responses
        that are given to the read

        :return: A list of addresses that responded to the read attempt
        :rtype: list
        """
        scan_responses = []
        self.transaction_logger.info("Performing bus scan")
        for addr in range(128):
            try:
                self.bus.read_byte(addr)
            except OSError:
                pass
            else:
                scan_responses.append(addr)
        self.transaction_logger.info(f"Scan got responses from: {scan_responses}")
        return scan_responses
