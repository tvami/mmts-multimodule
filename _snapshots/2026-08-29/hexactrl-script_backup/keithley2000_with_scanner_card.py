""" References: 
Keithley 2000 User Manual: https://download.tek.com/manual/2000-900_J-Aug2010_User.pdf
Keithley Scanner card Manual: https://www.testequity.com/documents/pdf/keithley/2000-SCAN-manual.pdf
PyMeasure library docs: https://pymeasure.readthedocs.io/en/latest/api/instruments/keithley/keithley2000.html
Single-Chip board schematic (J4/J7): https://edms.cern.ch/ui/file/2330957/1/1908_Schema_Socket.pdf """

from pymeasure.instruments import Instrument
from pymeasure.instruments.keithley import Keithley2000
from time import sleep

class Keithley2000WithScannerCard(Keithley2000):
    """ Represents the Keithley DMM with internal scanner card and provides a high-level
    interface for interacting with the instrument.  """

    SCANNER_CARD_MAP = { 
        'Ctest'     : 1,
        'AdcP'      : 2,
        'AdcN'      : 3,   # Temp probe for J7
        'Vdd_pll'   : 4,   # only on J4
        'Vdd_sc'    : 5,   # only on J4
        'Vbg_1V'    : 6,
        'Vgn'       : 7,
        'In_V'      : 8,   # Temp probe for J7
        'probe_dc'  : 9,
        'probe_calib'  : 10,
        }

    def __init__(self, adapter, **kwargs):
        super(Keithley2000WithScannerCard, self).__init__(adapter, **kwargs)
        self.reset()
        self.beep_state = 'disabled'  # disable system beep
        self.mode = "voltage"
        self.voltage_range = 10       # 0..10 V input range

    def config_buffer(self, points=64, delay=0):  # max buffer points: 1024
        super().config_buffer(points, delay)
        self.trigger_count = 1   # add one point per trigger to buffer

    def trigger(self):
        self.write("INIT;*WAI")

    channel = Instrument.control(
            ":ROUTE:CLOSE:STATE?", ":ROUTE:CLOSE (@%d)",
            """ Activate a scanner card channel. """,
            values=SCANNER_CARD_MAP,
            map_values=True,
            get_process=lambda v: int(v.strip("@()"))  # convert chanlist to number
            )

''' Usage example:
    from PrologixEthernetAdapter import PrologixEthernetAdapter
    adapter = PrologixEthernetAdapter('128.141.89.187', address=21)
    inst = Keithley2000WithScannerCard(adapter)

    inst.config_buffer(10)
    print(inst.is_buffer_full())

    inst.channel = "ProbeDC1"
    for i in range(inst.buffer_points):
        inst.trigger()

    print(inst.buffer_data)
    print(inst.is_buffer_full())
    print(inst.channel)
'''
