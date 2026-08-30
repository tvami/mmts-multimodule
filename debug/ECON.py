import logging
import numpy


class ECON:
    """
    Responsible for handling all interaction with the ECONs. Effectively wraps
    the ECON hardware interface.
    """

    def __init__(
        self,
        transport,
        base_address,
        name,
        cfg_converter,
        read_size=16,
        write_size=14,
        force_ones=None,
    ):
        """
        Software counterpart of the ECON ASIC to be used with the test
        systems.

        :param transport: Object that encapsulates how to write and read to the
            physical chip
        :type transport: object
        :param base_address: Base address of the ECON to read and write to
        :type base_address: int
        :param name: Name of the ECON
        :type name: str
        :param cfg_converter: CfgConverter object, used to convert between
        various user-friendly ways of specifying configuration and the
        low-level representations needed to do I2C transactions
        :type cgf_converter: CfgConverter
        :param read_size: Optional, maximum length of a multibyte I2C read
        :type read_size: int
        :param write_size: Optional, maximum length of a multibyte I2C write,
            excluding the 2 bytes used for the internal address
        :type write_size: int
        :param force_ones: Optional, used as a workaround for ECON-T to stop us
            from turning off the FC clock eRX
        :type force_ones: array
        """
        self.transaction_logger = logging.getLogger(f"{name}")
        self.transaction_logger.debug(
            f"Initializing {name}" f" at base address {base_address}"
        )
        self.name = name
        self.base_address = base_address
        self.transport = transport
        self.read_size = read_size
        self.write_size = write_size

        self.cfg_converter = cfg_converter
        self.force_ones = force_ones

        self.read_error_counter = 0
        self.write_error_counter = 0

        self.transaction_logger.debug("Initialization complete")

    def read_all(self):
        """
        Read all of the I2C registers from start to finish and return a bytes
        object.  The bytes object can be converted to a dictionary using the
        `bytes_to_ECON_dict` method if needed.
        """
        self.transport.write(
            address=self.base_address,
            data=None,
            internal_address=(0).to_bytes(2, "big"),
            log=False,
        )
        N = self.cfg_converter.total_length_bytes // self.read_size
        Nextra = self.cfg_converter.total_length_bytes % self.read_size
        data_that_we_read = []
        for i in range(N):
            data_that_we_read.append(
                self.transport.read(
                    address=self.base_address, count=self.read_size, log=False
                )
            )
        if Nextra > 0:
            data_that_we_read.append(
                self.transport.read(address=self.base_address, count=Nextra, log=False)
            )
        return b"".join(data_that_we_read)

    def write_all(self, data):
        """
        Write to all of the I2C registers start to finish.  The `data`
        parameter must be a bytes object with length equal to
        self.cfg_converter.total_length_bytes.  This may be constructed by
        passing a dictionary containing all register values to
        self.ECON_dict_to_bytes.
        """
        N = self.cfg_converter.total_length_bytes // self.write_size
        Nextra = self.cfg_converter.total_length_bytes % self.write_size

        if self.force_ones is not None:
            data = self.cfg_converter.array_to_bytes(
                self.cfg_converter.bytes_to_array(data) | self.force_ones
            )

        for i in range(N + 1 * (Nextra > 0)):
            for attempt in range(3):
                try:
                    self.transport.write(
                        address=self.base_address,
                        data=data[self.write_size * i : self.write_size * (i + 1)],
                        internal_address=(self.write_size * i).to_bytes(2, "big"),
                    )
                except OSError:
                    self.transaction_logger.debug(
                        f"Failed on attempt {attempt} at write {i} of {N}."
                    )
                    print(f"Failed on attempt {attempt} at write {i} of {N}.")
                    self.write_error_counter += 1
                    if attempt >= 2:
                        raise
                else:
                    break

    def read_some(self, mask_array):
        """
        Read only the I2C registers corresponding to non-zero values in
        mask_array.
        mask_array is a numpy array of dtype numpy.uint8
        Its length must be equal to self.cfg_converter.total_length_bytes
        Return a numpy array of dtype numpy.uint8 with length equal to
        self.total_length_bytes, with non-zero values only where mask_array was
        nonzero.

        This is intended for internal use. The `self.read` method provides a
        more user-friendly interface.
        """

        pos = 0
        out_array = numpy.zeros(
            self.cfg_converter.total_length_bytes, dtype=numpy.uint8
        )
        while any(mask_array[pos:] != 0):
            start = mask_array[pos:].nonzero()[0][0]
            end = mask_array[pos + start : pos + start + self.read_size].nonzero()[0][
                -1
            ]
            for attempt in range(3):
                try:
                    if start != 0 or pos == 0:
                        self.transport.write(
                            address=self.base_address,
                            data=None,
                            internal_address=int(pos + start).to_bytes(2, "big"),
                            log=False,
                        )
                    dat = self.transport.read(
                        address=self.base_address, count=int(end + 1), log=False
                    )
                except IOError as e:
                    self.transaction_logger.debug(
                        f"Failed on attempt {attempt} at read_some to position {pos}"
                    )
                    print(f"Failed on attempt {attempt} at read_some to position {pos}.")
                    self.read_error_counter += 1
                    if attempt >= 2:
                        raise
                else:
                    break

            out_array[pos + start : pos + start + end + 1] = numpy.frombuffer(
                dat, dtype=numpy.uint8
            )
            pos = pos + start + end + 1
        return out_array & mask_array

    def write_some(self, data_array, mask_array, read_first=True, read_from=None):
        """
        Write only the I2C registers corresponding to non-zero values in
        mask_array.
        data_array is a numpy array of dtype numpy.uint8 and length equal to
        self.cfg_converter.total_length_bytes.  It contains the data to be written.
        mask_array is a numpy array of dtype numpy.uint8 and length equal to
        self.cfg_converter.total_length_bytes.  Only I2C registers
        corresponding to nonzero values of mask_array will be written.
        If read_first is True, then any I2C registers corresponding to entries
        in mask_array that are neither 0 nor 0xff will be read first, so that
        the bits in those registers that we are not trying to write can be
        unchanged.  If read_first is False, then be WARNED: we will overwrite
        those bits even though mask_array seems to indicate they will not be
        changed.

        This is intended for internal use. The `self.configure` method provides
        a more user-friendly interface.
        """

        if read_first:
            if not read_from:
                pos = 0
                read_mask_array = numpy.zeros(
                    self.cfg_converter.total_length_bytes, dtype=numpy.uint8
                )
                while any(mask_array[pos:] != 0):
                    start = mask_array[pos:].nonzero()[0][0]
                    end = mask_array[
                        pos + start : pos + start + self.write_size
                    ].nonzero()[0][-1]
                    A, B = pos + start, pos + start + end + 1
                    read_mask_array[A:B] = self.cfg_converter.mask_array[A:B]
                    pos = B

                start_array = self.read_some(read_mask_array)
            else:
                start_array = self.cfg_converter.bytes_to_array(read_from)
            data_array = (start_array & (~mask_array)) | (data_array & mask_array)

        if self.force_ones is not None:
            data_array = data_array | self.force_ones

        pos = 0
        while any(mask_array[pos:] != 0):
            start = mask_array[pos:].nonzero()[0][0]
            end = mask_array[pos + start : pos + start + self.write_size].nonzero()[
                0
            ][-1]
            for attempt in range(3):
                try:
                    self.transport.write(
                        self.base_address,
                        bytes(data_array[pos + start : pos + start + end + 1]),
                        int(pos + start).to_bytes(2, "big"),
                        False,
                    )
                except OSError:
                    self.transaction_logger.debug(
                        f"Failed on attempt {attempt} at write_some to position {pos}"
                    )
                    print(f"Failed on attempt {attempt} at write_some to position {pos}.")
                    self.write_error_counter += 1
                    if attempt >= 2:
                        raise
                else:
                    break

            pos = pos + start + end + 1

    def configure(self, configuration: dict, readback=False, read_from=None):
        """
        Writes to ECON registers

        :param configuration: Configuration containing values to write
        :type configuration: dict
        :param readback: Specifies whether to check read written registers
            after writing. Defaults to False
        :type readback: bool, optional

        :return: The values of parameters read after readback (if
        readback=True, otherwise list is empty)
        :rtype: dict
        """
        try:
            self.cfg_converter._validate(configuration)
        except KeyError as err:
            raise KeyError(str(err.args[0]) + f" in ECON {self.name}")
        except ValueError as err:
            raise ValueError(str(err.args[0]) + f" in ECON {self.name}")

        data_dict, mask_dict = self.cfg_converter.configuration_to_dicts(configuration)
        data_array, mask_array = self.cfg_converter.dicts_to_arrays(
            data_dict, mask_dict
        )

        self.write_some(data_array, mask_array, read_from=read_from)

        param_readbacks = []
        if readback:
            param_readbacks = self.read(configuration)

        return param_readbacks

    def read(self, configuration):
        """
        :param configuration: Configuration containing parameters to read
        :type configuration: dict
        :return: The values of parameters read
        :rtype: tuple
        """
        try:
            self.cfg_converter._validate(configuration, read=True)
        except KeyError as err:
            raise KeyError(str(err.args[0]) + f" in ECON {self.name}")
        except ValueError as err:
            raise ValueError(str(err.args[0]) + f" in ECON {self.name}")

        self.transaction_logger.debug("Configuration to translate %s" % configuration)

        data_dict, mask_dict = self.cfg_converter.configuration_to_dicts(configuration)
        data_array, mask_array = self.cfg_converter.dicts_to_arrays(
            data_dict, mask_dict, use_data=False
        )

        try:
            out_array = self.read_some(mask_array)
            out_dict = self.cfg_converter.bytes_to_ECON_dict(
                self.cfg_converter.array_to_bytes(out_array)
            )
            out_params = self.cfg_converter.dict_to_out_parameters(
                configuration, out_dict
            )
        except OSError:
            # OS Error is raised from a NACK, in this case, return -1 for all parameters
            out_array = numpy.zeros(
                self.cfg_converter.total_length_bytes, dtype=numpy.uint8
            )
            out_dict = self.cfg_converter.bytes_to_ECON_dict(
                self.cfg_converter.array_to_bytes(out_array)
            )
            out_params = self.cfg_converter.dict_to_out_parameters(
                configuration, out_dict
            )
            for i in range(len(out_params)):
                out_params[i] = (out_params[i][0], -1)

        return out_params

    def set_base_address(self, new_base_address):
        self.base_address = new_base_address
