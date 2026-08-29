from smbus2 import SMBus
import gpiod
import subprocess
from typing import Union
from time import sleep

DEBUG = False

def i2cdetect(msg: str):
    """Debugging utility. Usage: `i2cdetect("Message printed before and after")`"""
    if not DEBUG:
        return
    print("\n", msg, sep="")
    print(subprocess.run("i2cdetect -y 2", shell=True, capture_output=True, text=True).stdout.rstrip())
    print(msg, "\n", sep="")

def reap_multiplex_holders():
    """Kill any leftover `gpioset -m signal -b` Multiplex holder from a previous
    LinkBuilder. That holder is backgrounded/detached (-b), so it OUTLIVES the
    server -- if the server crashed or was restarted, the stale holder keeps
    Multiplex_A/B busy and the next launch dies with 'Device or resource busy'.
    Matches this code's own invocation pattern (the manual B/C workflow uses the
    long-form `--mode=signal`, so an intentional external hold is left alone).
    Runs as daq, which owns these holders -- no sudo. No-op if none are running."""
    subprocess.run("pkill -f 'gpioset -m signal -b'", shell=True)
    sleep(0.2)  # let the kernel release the lines before we re-grab them

class LinkBuilder:
    def __init__(self, slot: Union[None, str] = None):
        """
        Args:
            slot (None | str):
                If not `None`, specifies which slot ("A", "B", or "C")
                in the multiplexed configuration
        """

        i2cs = {}
        gpios = {}

        multimodule = slot in ["A", "B", "C"]
        if multimodule:
            slot_int = ["A", "B", "C"].index(slot)
            if DEBUG:
                print(f"[MUX] slot = {repr(slot)}")
                print(f"[MUX] slot_int = {slot_int:#02b}")

            # Set the state of `Multiplex_A` and `Multiplex_B` digital outputs so that
            # the hexacontroller board reads the DAQ lines from the right slot (A, B, or C)
            multiplex_a = 1 & (slot_int >> 0) # Least significant bit
            multiplex_b = 1 & (slot_int >> 1) # 2nd least significant bit
            if DEBUG:
                print(f"[MUX] gpioset Multiplex_A = {multiplex_a}")
                print(f"[MUX] gpioset Multiplex_B = {multiplex_b}")
            reap_multiplex_holders()  # release any stale holder from a crashed/prior server
            subprocess.run(f"gpioset -m signal -b $(gpiofind Multiplex_A)={multiplex_a}", shell=True, check=True)
            subprocess.run(f"gpioset -m signal -b $(gpiofind Multiplex_B)={multiplex_b}", shell=True, check=True)
        try:
            i2cs.update(mux_i2c_discover(slot) if multimodule else xil_i2c_discover())
            gpios.update(mux_gpio_discover(slot) if multimodule else xil_gpio_discover())
        except (IOError):
            # Carry on with whatever was discovered, but never silently: an empty
            # dict here produces "0 links" and then a bare NameError on `board`
            # further up, which hides the actual bus error completely. Losing
            # either dict is enough to lose every link, since the links below are
            # the INTERSECTION of gpios and i2cs.
            import traceback
            print("[I2C] discovery raised, continuing with a partial map:")
            traceback.print_exc()

        try:
            import gbtsca_bus
            try:
                self.sca = gbtsca_bus.GBTSCA("gbt_sca_com_0","file://${UHAL_ADDRESS_TABLE}/connection.xml", "mylittlememory")
                self.sca.reset_gbtsca()
            except(gbtsca_bus.sca.gbtsca_exception.GBT_SCA_Exception):
                pass

            try:
                gpios.update(sca_gpio_discover(self.sca))
                for gpio_name, gpio in gpios.items():
                    gpio.write(1)
                i2cs.update(sca_i2c_discover(self.sca))
            except(gbtsca_bus.sca.gbtsca_exception.GBT_SCA_Exception):
                pass

        except(ImportError):
            pass

        self.links = {}
        for gpio_name, gpio in gpios.items():
            for i2c_name, i2c in i2cs.items():
                if gpio_name in i2c_name:
                    self.links[i2c_name] = Link(i2c, gpio)

class Link:
    def __init__(self, i2c, gpio):
        self.i2c = i2c
        self.gpio = gpio

class i2c():
    def __init__(self, addr, bus, sca=0):
        self._addr = addr
        self._bus = bus
        self._sca = sca

    def write(self, *args, **kwargs):
        raise NotImplementedError

    def read(self, *args, **kwargs):
        raise NotImplementedError

class sca_i2c(i2c):
    def write(self, offset, byte):
       with self._sca.scabus(self._bus) as bus:
            bus.write_byte(self._addr + offset, byte)
       return None
    
    def read(self, offset):
       with self._sca.scabus(self._bus) as bus:
            ret = bus.read_byte(self._addr + offset)
       return ret

def sca_i2c_discover(sca):
    """ Discover all ROCs on gbtsca i2c """

    rocs = []
    sca.enableI2C(0xffff)
    for bus_id in range(15):  # 8 i2c bus lines
        try:
            with sca.scabus(bus_id) as bus:
                addrs = []
                for addr in range(128):  # 128 addrs per bus line
                    try:
                        bus.read_byte(addr)
                        addrs.append(addr)
                    except Exception as e:
                        pass # skip non-existing addr
                print('[I2C] Found %d address(es) on bus %d' % (len(addrs),bus_id))
                if len(addrs) >= 8: 
                    rocs.append((addrs[0], bus_id))
                if len(addrs) == 16:
                    rocs.append((addrs[8], bus_id))
        except Exception as e:
            pass  # skip undefined i2c busses
    return sca_i2c_create(rocs,sca)

def sca_i2c_create(rocs,sca):
    """ Detect board type & create i2c objects """

    # n = len(rocs)
    # if n == 1:   
    #     print('[I2C] Identified Single-Chip (Char) board')
    #     roc_map = i2c_char_map
    # elif n == 3: 
    #     print('[I2C] Identified LD HexaBoard')
    #     roc_map = i2c_ld_map
    # elif n == 6: 
    #     print('[I2C] Identified HD HexaBoard')
    #     roc_map = i2c_hd_map

    board_name, roc_map = get_i2c_map_for_rocs(rocs)
    print(f'[I2C] Board identification: {board_name}')

    return {roc_map[addr]:sca_i2c(addr,bus,sca) for (addr, bus) in rocs}

class xil_i2c(i2c):
    def write(self, offset, byte):
        with SMBus(self._bus) as bus:
            bus.write_byte(self._addr + offset, byte)
        return None

    def read(self, offset):
        with SMBus(self._bus) as bus:
            ret = bus.read_byte(self._addr + offset)
        return ret

i2c_maps = {
    'Characterisation Board':
        {0x0: 'roc_s0'},
    'Old ROCv2 LD HB':
        {0x00: 'roc_s0', 0x40: 'roc_s1', 0x20: 'roc_s2'},
    'NSH HB':
        {0x60: 'roc_s0', 0x40: 'roc_s1', 0x20: 'roc_s2'},
    'V3 LD Full HB':
        {0x08: 'roc_s0', 0x18: 'roc_s1', 0x28: 'roc_s2'},
    'V3 LD Five HB':
        {0x48: 'roc_s0', 0x58: 'roc_s1', 0x68: 'roc_s2'},
    'V3 LD Semi or Half HB':
        {0x48: 'roc_s0', 0x58: 'roc_s1'},
    'V3 HD Full HB':
        {0x08: 'roc_s0_0', 0x48: 'roc_s0_1',
         0x18: 'roc_s1_0', 0x58: 'roc_s1_1',
         0x28: 'roc_s2_0', 0x68: 'roc_s2_1'},
    'V3 HD Semi-left or HD Semi-right HB':
        {0x08: 'roc_s0_0', 0x18: 'roc_s1_0'},
     'V3 HD Bottom HB':
        {0x18: 'roc_s0_0', 0x58: 'roc_s0_1',
         0x28: 'roc_s1_0', 0x68: 'roc_s1_1'},
     'V3 HD Top HB':
        {0x18: 'roc_s0_0', 0x58: 'roc_s0_1', 0x28: 'roc_s1_0'},
}

def find_board_for_rocs(detected_roc_addrs):
    for board_name, board_map in i2c_maps.items():
        board_roc_addrs = board_map.keys()
        if set(board_roc_addrs) == set([addr for (addr, bus) in detected_roc_addrs]):
            return board_name
    else:
            return None

def get_i2c_map_for_rocs(roc_addrs):
    board_name = find_board_for_rocs(roc_addrs)
    try:
        return board_name, i2c_maps[board_name]
    except:
        return f"ROC addresses {['0x%02X'%addr for addr, sub_bus in roc_addrs]} do not match a known board", {}

def xil_i2c_discover():
    """ Discover all ROCs on i2c """

    rocs = []
    for bus_id in range(8):  # 8 i2c bus lines
        try:
            with SMBus(bus_id) as bus:
                addrs = []
                for addr in range(128):  # 128 addrs per bus line
                    try:
                        bus.read_byte(addr)
                        addrs.append(addr)
                    except IOError as e: 
                        pass # skip non-existing addr
                print('[I2C] Found %d address(es) on bus %d' % (len(addrs),bus_id))
                if len(addrs) >= 8:
                    rocs.append((addrs[0], bus_id))
                if len(addrs) >= 16:
                    rocs.append((addrs[8], bus_id))
                if len(addrs) >= 24:
                    rocs.append((addrs[16], bus_id))
                if len(addrs) >= 32:
                    rocs.append((addrs[24], bus_id))
                if len(addrs) >= 40:
                    rocs.append((addrs[32], bus_id))
                if len(addrs) >= 48:
                    rocs.append((addrs[40], bus_id))
        except FileNotFoundError:
            pass  # skip undefined i2c busses
    return xil_i2c_create(rocs)

def xil_i2c_create(rocs):
    """ Detect board type & create i2c objects """
    board_name, roc_map = get_i2c_map_for_rocs(rocs)
    print(f'[I2C] Board identification: {board_name}')

    return {roc_map[addr]:xil_i2c(addr,bus) for (addr, bus) in rocs}

class gpio():
    def __init__(self, lines):
        self._lines = lines

    def write(self, *args, **kwargs):
        raise NotImplementedError
    
    def read(self, *args, **kwargs):
        raise NotImplementedError

gpio_tbtester_map = {'roc_s0':[('hgcroc_soft_rstB',0x4), ('hgcroc_i2c_rstB',0x8), ('hgcroc_hard_rstB',0x10)]}
gpio_tbtester_noresetmap = {'roc_s0':[('EN_LDO',0x400000), ('SOFTSTART',0x800000)]}

class sca_gpio(gpio):
    def write(self, val):
       for line in self._lines:
            line.set_value(val)
  
    def read(self):
        ans = { }
        for line in self._lines:
            ans[line.name] = line.get_value()
        return ans
 
    def reset(self):
        self._lines[0].reset_rocs()

def sca_gpio_discover(sca):
    lines = []
    sca.enableGPIO(True)
    for name in gpio_tbtester_map['roc_s0']:
        lines.append(sca.gpio(name[0],name[1],False));
    for name in gpio_tbtester_noresetmap['roc_s0']:
        line = sca.gpio(name[0],name[1],False)
        line.set_value(1)
    return {'roc_s0' : sca_gpio(lines)}   

class xil_gpio(gpio):

    def write(self, val):
        for line in self._lines:
            config = gpiod.line_request()
            config.consumer = "xil_gpio_write"
            config.request_type = gpiod.line_request.DIRECTION_OUTPUT
            line.request(config)
            line.set_value(val)
            line.release()

    def read(self):
        ans = {}
        for line in self._lines:
            config = gpiod.line_request()
            config.consumer = "xil_gpio_read"
            config.request_type = gpiod.line_request.DIRECTION_INPUT
            line.request(config)
            ans[line.name] = line.get_value()
        return ans

gpio_char_map = {'roc_s0': ['hgcroc_rstB', 'resyncload', 'hgcroc_i2c_rstB']}

## for trophy v1 and v2
gpio_hexa_map_v1 = {'roc_s0': ['s0_resetn', 's0_i2c_rstn'], 
                    'roc_s1': ['s1_resetn', 's1_i2c_rstn'], 
                    'roc_s2': ['s2_resetn', 's2_i2c_rstn']}

## for trophy v3
gpio_hexa_map_v3 = {'roc_s0': ['s1_resetn', 'hard_resetn'], 
                    'roc_s1': ['s2_resetn', 'hard_resetn'], 
                    'roc_s2': ['s3_resetn', 'hard_resetn']}

def xil_gpio_discover():
    # get all lines on all connected gpio chips
    lines = []
    for chip in gpiod.chip_iter():
        for line in gpiod.line_iter(chip):
            lines.append(line)
    print([l.name for l in lines],'hgcroc_rstB' in [l.name for l in lines])        
    if 'hgcroc_rstB' in [l.name for l in lines]:
        gpio_map = gpio_char_map
    elif 's0_i2c_rstn' in [l.name for l in lines]:
        gpio_map = gpio_hexa_map_v1
    elif 'hard_resetn' in [l.name for l in lines]:
        gpio_map = gpio_hexa_map_v3
    else:
        print("ERROR : fail to find correct GPIO map in xil_gpio_discover")
        gpio_map = {}

    print("[GPIO] Identified gpio map : ",gpio_map)
    ret = {}
    print(gpio_map)
    for roc, line_names in gpio_map.items():
        sel_names = set(line_names).intersection([l.name for l in lines])
        if sel_names:
            ret[roc] = xil_gpio([l for l in lines if l.name in sel_names])
    if ret: return ret
    else: raise('Missing HexaBoard GPIO lines.')


def testAutomaticDetection():
    #only used to test correct board detection can be achieved

    #Characterisation Board
    rocs = [(0x28,2)]
    myboard = xil_i2c_create(rocs)

    #Old ROCv2 LD HB
    rocs = [(0x00,5),(0x40,6),(0x20,7)]
    myboard = xil_i2c_create(rocs)

    #NSH HB
    rocs = [(0x60,5),(0x40,6),(0x20,7)]
    myboard = xil_i2c_create(rocs)

    #LD full
    rocs = [(0x08,2),(0x18,2),(0x28,2)]
    myboard = xil_i2c_create(rocs)

    #LD partial
    rocs = [(0x48,2),(0x58,2)]
    myboard = xil_i2c_create(rocs)

    #HD full
    rocs = [ (0x08,2),(0x48,2),
             (0x18,3),(0x58,3),
             (0x28,4),(0x68,4) ]
    myboard = xil_i2c_create(rocs)
    
# Multimodule test bench topology:
#
# Hexacontroller
# ╰── Bus 2
MUX_MASTER_BUS = 2
#     ├── 0x71 PCA9848 1-to-8 I2C bus switch (slot A)
#     │   ╰── ... (see below for details)
#     ├── 0x73 PCA9848 1-to-8 I2C bus switch (slot B)
#     │   ╰── ... (see below for details)
#     ╰── 0x77 PCA9848 1-to-8 I2C bus switch (slot C)
#         ├── Sub-bus 0x01 / 0b00000001 "PWR"
#         ├── Sub-bus 0x02 / 0b00000010 "S1_I2C"
#         ├── Sub-bus 0x04 / 0b00000100 "S2"
#         │   ╰── Trophy board mezzanine components; ADCs, EEPROM
#         ├── Sub-bus 0x08 / 0b00001000 "S2_I2C"
#         ├── Sub-bus 0x10 / 0b00010000 "Spare" (power management board)
#         │   ├── 0x26 TCA9535 on the power management board
#         │   ╰── 0x?? LTC2497 on the power management board
#         ├── Sub-bus 0x20 / 0b00100000 "Sgl" (GPIO controllers)
#         │   ├── 0x20 TCAL6416 I2C GPIO controller
#         │   │   ╰── ... (see MUX_GPIO below for details)
#         │   ╰── 0x21 TCAL6416 I2C GPIO controller
#         │       ╰── ... (see MUX_GPIO below for details)
#         ├── Sub-bus 0x40 / 0b01000000 "S1"
#         ╰── Sub-bus 0x80 / 0b10000000 "S3_I2C"

def get_i2c_bus_switch(slot: str) -> int:
    if slot in ["A", "B", "C"]:
        return {"A": 0x71, "B": 0x73, "C": 0x77}[slot]
    raise ValueError(f"`slot` must be either {repr('A')}, {repr('B')}, or {repr('C')}; got {repr(slot)}")

# Which sub-bus each PCA9848 switch is currently pointing at, so a run of accesses
# to the same device does not re-select it every time.
#
# Opening the sub-bus, moving one byte and closing it again -- once per byte, the
# way this code used to -- wedges the Alabama bench's PL master after ~3
# transactions. The same traffic with the sub-bus left open runs indefinitely
# (600/600 clean). So select lazily and leave the selection standing; a switch is
# only ever closed when a DIFFERENT switch has to be opened, which keeps two slots
# from presenting the same ROC addresses to the master at once.
_mux_subbus_state: dict[int, int] = {}

def mux_select(bus, switch: int, sub_bus: int):
    """Point one PCA9848 at `sub_bus`, skipping the write if it already is."""
    for other, current in list(_mux_subbus_state.items()):
        if other != switch and current:
            bus.write_byte(other, 0x00)
            _mux_subbus_state[other] = 0
    if _mux_subbus_state.get(switch) != sub_bus:
        bus.write_byte(switch, sub_bus)
        _mux_subbus_state[switch] = sub_bus

def mux_forget_selection():
    """Drop the cached selection after an error or a direct switch write, so the
    next access re-selects instead of trusting a state that may not hold."""
    _mux_subbus_state.clear()

class mux_i2c(i2c):
    """
    Handle I2C communications through the multiplexer board
    and its PCA9848 I2C bus switches
    """
    def __init__(self, addr: int, bus: int, slot: str):
        """
        Args:
            addr (int): I2C device address between 0 and 127
            bus (int): Slot sub-bus number between 0 and 7
            slot (str): Module multiplexer board slot ("A", "B", or "C")
        """
        super().__init__(addr, bus)
        self._slot = slot
        self._i2c_bus_switch = get_i2c_bus_switch(slot)
        if DEBUG:
            print(f"[MUX] {self}")

    def write(self, offset, byte):
        with SMBus(MUX_MASTER_BUS) as bus:
            try:
                mux_select(bus, self._i2c_bus_switch, 1 << self._bus)
                bus.write_byte(self._addr + offset, byte)
            except OSError:
                mux_forget_selection()
                raise
        return None

    def read(self, offset):
        with SMBus(MUX_MASTER_BUS) as bus:
            try:
                mux_select(bus, self._i2c_bus_switch, 1 << self._bus)
                ret = bus.read_byte(self._addr + offset)
            except OSError:
                mux_forget_selection()
                raise
        return ret

    def __repr__(self):
        return f"mux_i2c(addr={self._addr:#04x}, bus={self._bus}, slot={repr(self._slot)})"

    def __str__(self):
        return " ".join([
            "(muxed I2C device @",
            f"slot {repr(self._slot)}",
            f"(I2C mux addr {self._i2c_bus_switch:#04x}),",
            f"sub-bus {self._bus},",
            f"addr {self._addr:#04x})",
        ])

def mux_i2c_discover(slot: str) -> dict[str, mux_i2c]:
    """
    Discover all HGCROCs on I2C

    Args:
        slot (str): Module multiplexer board slot ("A", "B", or "C")
    """
    i2c_bus_switch = get_i2c_bus_switch(slot)
    if DEBUG:
        print(f"[MUX] mux_i2c_discover(slot={repr(slot)})")
        print(f"[MUX] (I2C mux addr {i2c_bus_switch:#04x})")
    sleep(1) # A short delay is needed to find all HGCROCs reliably

    rocs: list[tuple[int, int]] = []
    # Iterate over each PCA9848 ROC sub-bus
    #        = 0x01 = sub-bus #0 =   1
    # S1_I2C = 0x02 = sub-bus #1 =   2
    #        = 0x04 = sub-bus #2 =   4
    # S2_I2C = 0x08 = sub-bus #3 =   8
    #        = 0x10 = sub-bus #4 =  16
    #        = 0x20 = sub-bus #5 =  32
    #        = 0x40 = sub-bus #6 =  64
    # S3_I2C = 0x80 = sub-bus #7 = 128
    #
    # Probe ONLY the known V3 HGCROC base addresses instead of sweeping every
    # address and picking ROC bases by position (addrs[0], addrs[8], ...). The
    # positional sweep is fragile: when a GPIO expander (0x20/0x21) appears on a
    # ROC sub-bus the indices shift and it mis-picks 0x20 as a ROC -> the base set
    # matches no board -> crash; the full 0x08-0x70 read sweep is also what can
    # wedge the write-mostly bus. Every V3 ROC base (LD and HD) has low nibble 0x8:
    # LD uses {0x08,0x18,0x28}, HD adds {0x48,0x58,0x68}. Probing just these finds
    # all ROCs wherever they sit, never mistakes the 2-address 0x20/0x21 expander
    # for a ROC, and issues ~6 reads/sub-bus instead of ~100.
    # NOTE: legacy ROCv2/NSH bases {0x00,0x20,0x40,0x60} are intentionally NOT probed
    # (0x20 collides with the GPIO expander); add them below only if you need them.
    candidate_bases = [0x08, 0x18, 0x28, 0x48, 0x58, 0x68]
    for sub_bus in MUX_SUBBUSES:
        with SMBus(MUX_MASTER_BUS) as bus:
            mux_select(bus, i2c_bus_switch, 1 << sub_bus)
        try:
            with SMBus(MUX_MASTER_BUS) as bus:
                found = []
                for base in candidate_bases:
                    try:
                        bus.read_byte(base)
                        rocs.append((base, sub_bus))
                        found.append(base)
                    except IOError:
                        pass # No ROC at this base on this sub-bus
                print(f"[I2C] Sub-bus {sub_bus}: ROC base(s) "
                      + (" ".join(f"0x{b:02x}" for b in found) if found else "(none)"))
        except FileNotFoundError:
            pass # Skip undefined I2C buses

    # The selection is deliberately left standing -- see mux_select().

    for addr, sub_bus in rocs:
        print(f"[I2C] (address {addr:#04x}, bus {MUX_MASTER_BUS}, sub-bus {sub_bus})")
    return mux_i2c_create(rocs, slot)

def mux_i2c_create(rocs: list[tuple[int, int]], slot: str) -> dict[str, mux_i2c]:
    """
    Detect board type & create I2C objects

    Args:
        slot (str): Module multiplexer board slot ("A", "B", or "C")
    """
    if DEBUG:
        print(
            "[MUX] mux_i2c_create(rocs=[",
            ",".join([f"({addr:#04x},{sub_bus})" for addr, sub_bus in rocs]),
            f"], slot={repr(slot)})",
            sep=""
        )
    board_name, roc_map = get_i2c_map_for_rocs(rocs)
    if roc_map:
        print(f"[I2C] Board identification: {board_name}")
        return {roc_map[addr]: mux_i2c(addr, bus, slot) for (addr, bus) in rocs}
    raise Exception(board_name)

class mux_gpio_line:
    def __init__(self, name: str, addr: int, port: int, pin: int):
        """
        TCAL6416 pin. Datasheet: https://www.ti.com/lit/ds/symlink/tcal6416.pdf.

        Args:
            name (str): Signal name
            addr (int): TCAL6416 I2C address (`0x20` or `0x21`)
            port (int): TCAL6416 port (`0` or `1`)
            pin (int):  Pin number (`0`...`7`)
        """
        if addr not in [0x20, 0x21]:
            raise ValueError(f"TCAL6416 I2C address is 0x20 or 0x21; got {addr:#04x}")
        if port not in [0, 1]:
            raise ValueError(f"TCAL6416 port is either 0 or 1; got {port}")
        if pin not in list(range(8)):
            raise ValueError(f"TCAL6416 pin is 0...7; got {pin}")
        self.name = name
        self.addr = addr
        self.port = port
        self.pin  = pin

        self._bit_pos = (1 << self.pin)         # Pin bitmask
        self._bit_inv = (1 << self.pin) ^ 0xFF  # Pin bitmask (inverted)
        self._reg_in  = [0x00, 0x01][self.port] # R    Input register address
        self._reg_out = [0x02, 0x03][self.port] # R/W  Output register address
        self._reg_pol = [0x04, 0x05][self.port] # R/W  Polarity register address
        self._reg_dir = [0x06, 0x07][self.port] # R/W  Direction (input/output) register address

        if DEBUG:
            print(f"[MUX] {self}")

    def __repr__(self):
        return f"mux_gpio_line({repr(self.name)}, addr={self.addr:#04x}, port={self.port}, pin={self.pin})"

    def __str__(self):
        return f"TCAL6416 @ {self.addr:#04x}, P{self.port}{self.pin} {repr(self.name)}"

# On the multimodule test bench, the GPIOs are no longer on the hexacontroller
# but on TCAL6416 GPIO controllers found on the multimodule multiplexer board.
# Such GPIOs cannot be discovered automatically, and are thus hardcoded below.
MUX_GPIO: list[mux_gpio_line] = [
  # mux_gpio_line("",            addr = 0x20, port = 0, pin = 0), # P00 Not Connected
    mux_gpio_line("s1_rstb",     addr = 0x20, port = 0, pin = 1), # P01
    mux_gpio_line("s2_rstb",     addr = 0x20, port = 0, pin = 2), # P02
    mux_gpio_line("s3_rstb",     addr = 0x20, port = 0, pin = 3), # P03
    mux_gpio_line("fmc_error",   addr = 0x20, port = 0, pin = 4), # P04
    mux_gpio_line("s2_error_l",  addr = 0x20, port = 0, pin = 5), # P05
    mux_gpio_line("s3_error_l",  addr = 0x20, port = 0, pin = 6), # P06
    mux_gpio_line("s1_error_r",  addr = 0x20, port = 0, pin = 7), # P07

    mux_gpio_line("s2_error_r",  addr = 0x20, port = 1, pin = 0), # P10
    mux_gpio_line("s3_error_r",  addr = 0x20, port = 1, pin = 1), # P11
    mux_gpio_line("s1_pwr_en",   addr = 0x20, port = 1, pin = 2), # P12
    mux_gpio_line("s2_pwr_en",   addr = 0x20, port = 1, pin = 3), # P13
    mux_gpio_line("s3_pwr_en",   addr = 0x20, port = 1, pin = 4), # P14
    mux_gpio_line("s1_pwr_pg",   addr = 0x20, port = 1, pin = 5), # P15
    mux_gpio_line("s2_pwr_pg",   addr = 0x20, port = 1, pin = 6), # P16
    mux_gpio_line("s3_pwr_pg",   addr = 0x20, port = 1, pin = 7), # P17

    mux_gpio_line("adc_rdy_pwr", addr = 0x21, port = 0, pin = 0), # P00
    mux_gpio_line("adc_rdy_s1",  addr = 0x21, port = 0, pin = 1), # P01
    mux_gpio_line("adc_rdy_s2",  addr = 0x21, port = 0, pin = 2), # P02
    mux_gpio_line("adc_rdy_s3",  addr = 0x21, port = 0, pin = 3), # P03
    mux_gpio_line("s1_i2c_rst",  addr = 0x21, port = 0, pin = 4), # P04
    mux_gpio_line("s2_i2c_rst",  addr = 0x21, port = 0, pin = 5), # P05
    mux_gpio_line("s3_i2c_rst",  addr = 0x21, port = 0, pin = 6), # P06
  # mux_gpio_line("",            addr = 0x21, port = 0, pin = 7), # P07 Not Connected

  # mux_gpio_line("",            addr = 0x21, port = 1, pin = 0), # P10 Not Connected
  # mux_gpio_line("",            addr = 0x21, port = 1, pin = 1), # P11 Not Connected
    mux_gpio_line("pg_dcdc",     addr = 0x21, port = 1, pin = 2), # P12
  # mux_gpio_line("",            addr = 0x21, port = 1, pin = 3), # P13 Not Connected
  # mux_gpio_line("",            addr = 0x21, port = 1, pin = 4), # P14 Not Connected
  # mux_gpio_line("",            addr = 0x21, port = 1, pin = 5), # P15 Not Connected
  # mux_gpio_line("",            addr = 0x21, port = 1, pin = 6), # P16 Not Connected
  # mux_gpio_line("",            addr = 0x21, port = 1, pin = 7), # P17 Not Connected
]

MUX_GPIO_MAP: dict[str, mux_gpio_line] = {line.name: line for line in MUX_GPIO}

class mux_gpio(gpio):
    def __init__(self, slot: str, lines: list[mux_gpio_line]):
        self._lines: list[mux_gpio_line] # Type hint
        super().__init__(lines)

        self._slot = slot
        self._i2c_bus_switch = get_i2c_bus_switch(slot)

    def __repr__(self):
        print(f"mux_gpio(slot={repr(slot)}, lines=[")
        for line in lines:
            print(f"  {repr(line)},")
        print("])")

    def write(self, val):
        """No-op: the mux board's reset lines are owned by the bring-up script.

        This is reached only from ROC.reset(), and on a multiplexer board that call
        is a category error. S*_RSTB is a per-SLOT line on the board's TCAL6416, not
        a per-ROC one, so resetting any one of a slot's three ROCs resets the whole
        module -- and zmq_server builds the board twice (once to identify the ROC
        type, once for real), resetting every ROC each time. The bring-up script
        releases RSTB immediately before the server starts, which is the reset that
        actually matters, so every toggle here is redundant.

        It is also actively harmful: driving these lines wedges the write-mostly PL
        master. On Alabama/kria4, two runs on a rested bench failed 8-for-8 selecting
        the GPIO sub-bus from here, and startup got no further. (The pre-merge
        server disabled ROC reset as well -- "GPIO reset skipped for now [FIXME]" --
        same conclusion, less explanation.)

        The read-modify-write this used to do is in git history if a bench ever needs
        the server to drive RSTB itself. It would need to reset one slot once, not
        once per ROC per board build.
        """
        if DEBUG:
            print(f"[MUX] skipping mux_gpio.write({val}); RSTB is owned by bring-up")
        return

    def read(self):
        raise NotImplementedError

def mux_gpio_discover(slot: str) -> dict[str, mux_gpio]:
    gpio_map = {"roc_s0": ["s1_rstb", "s1_i2c_rst"],
                "roc_s1": ["s2_rstb", "s2_i2c_rst"],
                "roc_s2": ["s3_rstb", "s3_i2c_rst"]}
    ret = {}
    for roc, line_names in gpio_map.items():
        ret[roc] = mux_gpio(slot, [line for line in MUX_GPIO if line.name in line_names])
    if ret:
        return ret
    raise Exception("Missing HexaBoard GPIO lines.")

class mux_gpio_lines:
    """
    A set of GPIOs from the same GPIO controller (@ 0x20 or 0x21),
    the same port (0 or 1), and the same purpose, meant to be read
    from and written to at once.
    """
    def __init__(self, lines: list[mux_gpio_line]):
        self.addr = lines[0].addr
        self._reg_dir = lines[0]._reg_dir
        self._reg_out = lines[0]._reg_out
        self._bit_pos = 0
        for line in lines:
            self._bit_pos = self._bit_pos | line._bit_pos
        self._bit_inv = self._bit_pos ^ 0xFF

# The multiplexer board has NO power management board on either MMTS bench -- the
# hexaboards are powered via the per-module TCAL6416 expanders (0x20/0x21) by the
# bring-up script (enableROCs.py at FNAL, enableROCs_alabama.py at Alabama, which
# drives the power management board itself before the server ever starts). Writing
# to an absent power-mgmt board on the shared master WEDGES it (Errno 110/5), so
# skip that step. Set True only on a bench where the server owns the power sequence.
MUX_HAS_POWER_MGMT_BOARD = False

# Sub-buses that mux_i2c_discover probes for ROCs. Selecting a sub-bus that hangs
# the bus is UNRECOVERABLE, so only sub-buses known to carry ROCs are probed.
# Sub-bus 7 used to be on this list and must not go back: on Alabama/kria4 slot C,
# selecting TO it succeeds and selecting AWAY from it never does -- neither to a ROC
# sub-bus nor to 0x00 -- which is what a device holding SDA low once connected looks
# like, since the master can then no longer issue a start. Worse, a PCA9848 keeps its
# selection across process exits, so discovery leaving sub-bus 7 standing means the
# NEXT server launch dies in mux_setup before running any logic of its own. Both
# benches carry their ROCs on sub-bus 1, so nothing is lost by not probing 7.
MUX_SUBBUSES = [1, 3]

# Power management board ADDR0, ADDR1, ADDR2 jumpers (False = no jumper, True = jumper)
POWER_MGMT_BOARD_ADDR_JUMPERS = {2: False, 1: False, 0: False}
POWER_MGMT_BOARD_ADDR = sum([has_jumper << bit for bit, has_jumper in POWER_MGMT_BOARD_ADDR_JUMPERS.items()])
#                         ---   --0   -1-   -10   2--   2-0   21-   210
POWER_MGMT_BOARD_GPIO = (0x27, 0x26, 0x25, 0x24, 0x23, 0x22, 0x21, 0x20)[POWER_MGMT_BOARD_ADDR]
POWER_MGMT_BOARD_ADC  = (0x76, 0x74, 0x64, 0x56, 0x34, 0x26, 0x16, 0x14)[POWER_MGMT_BOARD_ADDR]

def _mux_setup_once(slot: str):
    """One attempt at mux_setup(); see there for what this does.

    Raises OSError if any access on the shared master fails, leaving it to
    mux_setup() to decide whether that was a transient worth retrying.
    """
    PWR_EN = mux_gpio_lines([
        MUX_GPIO_MAP["s1_pwr_en"],
        MUX_GPIO_MAP["s2_pwr_en"],
        MUX_GPIO_MAP["s3_pwr_en"],
    ])
    RSTB = mux_gpio_lines([
        MUX_GPIO_MAP["s1_rstb"],
        MUX_GPIO_MAP["s2_rstb"],
        MUX_GPIO_MAP["s3_rstb"],
    ])
    I2C_RST = mux_gpio_lines([
        MUX_GPIO_MAP["s1_i2c_rst"],
        MUX_GPIO_MAP["s2_i2c_rst"],
        MUX_GPIO_MAP["s3_i2c_rst"],
    ])

    if DEBUG:
        print(f"[MUX] Power management board ADDR jumpers: {POWER_MGMT_BOARD_ADDR_JUMPERS}")
        print(f"[MUX] Power management board GPIO address: {POWER_MGMT_BOARD_GPIO:#04x}")

    # This function drives the PCA9848s directly, so any cached selection from
    # earlier accesses no longer describes the hardware.
    mux_forget_selection()

    def _writes(writes, attempts=5):
        """One retried group: fresh fd -> select "Sgl" -> two register writes.

        Retry in SMALL groups, not one six-write block. On a degrading bus each
        transaction has an independent chance of an EIO, so the chance a group
        survives falls exponentially with its length: the six expander writes
        under one selection were failing 5/5 while enableROCs_alabama's _seq() --
        same expander, same switch, two writes per retried group -- was getting
        through with 2-3 retries. Each attempt restarts from a fresh SMBus fd and
        a fresh select so a half-finished group always re-runs clean; every write
        is an absolute value, so re-issuing is idempotent.

        The select is a single write of the target channel: the PCA9848 control
        register is one-hot, so 0x20 clears every other channel by itself, and a
        preceding 0x00 write would just spend switch-toggle headroom (this bench
        wedges on toggling; a standing selection ran 600/600 clean).
        """
        last = None
        for attempt in range(attempts):
            try:
                with SMBus(MUX_MASTER_BUS) as bus:
                    bus.write_byte(get_i2c_bus_switch(slot), 0x20) # "Sgl" sub-bus
                    for addr, reg, val in writes:
                        bus.write_byte_data(addr, reg, val)
                return
            except OSError as e:
                last = e
                print(f"IOError in mux_setup group (attempt {attempt+1}/{attempts}): {e}. Retrying.")
                sleep(0.2 * (attempt + 1))
        raise last

    ##############################
    ### Power management board ###
    # Skipped on the MMTS bench (no power management board). Connecting the "Spare"
    # sub-bus and writing to an absent board wedges the shared master (Errno 110/5),
    # which then kills the switch writes below. See MUX_HAS_POWER_MGMT_BOARD above.
    if MUX_HAS_POWER_MGMT_BOARD:
        with SMBus(MUX_MASTER_BUS) as bus:
            # Connect the hexacontroller to the power management board
            bus.write_byte(get_i2c_bus_switch(slot), 0x10) # "Spare" sub-bus (power management board)

            i2cdetect("Power management board")
            mask = {"A": 0b001, "B": 0b010, "C": 0b100}[slot]
            try:
                # TCA9535 @ 0x26, P00/P01/P02 'EN_M1/2/3' output direction
                bus.write_byte_data(POWER_MGMT_BOARD_GPIO, 0x06, 0xF8) # 0b11111000 port 0 direction
                # TCA9535 @ 0x26, P00/P01/P02 'EN_M1/2/3' HIGH state
                bus.write_byte_data(POWER_MGMT_BOARD_GPIO, 0x02, mask) # 0b00000??? port 0 output (??? = 001, 010, or 100)
            except Exception as e:
                print(e)
                pass # No power management board is used, or there is an I2C error

    #########################
    ### Multiplexer board ###
    #
    # The mux board TCAL6416 GPIO controllers for this slot -- THIS SLOT ONLY.
    # Every slot's expanders live at the same two addresses (0x20/0x21) behind
    # its own PCA9848, so selecting the "Sgl" sub-bus on more than one switch
    # puts two devices on 0x20 at once. Broadcast WRITES survive that (same
    # register, same value, both accept); reads do not, and the read-modify-write
    # in mux_gpio.write() then returns garbage from an arbitrary one of them.
    # A switch that is not populated NACKs and wedges the master outright. The
    # server is launched for one slot and configures one slot.

    # TCAL6416 @ 0x20, P12/P13/P14 'S1/S2/S3_PWR_EN': output direction, then HIGH
    _writes([(PWR_EN.addr, PWR_EN._reg_dir, PWR_EN._bit_inv),   # (0x20, 0x07, 0xE3)
             (PWR_EN.addr, PWR_EN._reg_out, PWR_EN._bit_pos)])  # (0x20, 0x03, 0x1C)

    # TCAL6416 @ 0x20, P01/P02/P03 'S1/S2/S3_RSTB': output direction, then HIGH
    _writes([(RSTB.addr, RSTB._reg_dir, RSTB._bit_inv),         # (0x20, 0x06, 0xF1)
             (RSTB.addr, RSTB._reg_out, RSTB._bit_pos)])        # (0x20, 0x02, 0x0E)

    # TCAL6416 @ 0x21, P04/P05/P06 'S1/S2/S3_I2C_RST': output direction, then HIGH.
    # The second write is the OUTPUT register; repeating _reg_dir here puts 0x70
    # in the direction register, which turns P04-P06 back into inputs and makes
    # the other five port-0 pins outputs. Symptom: all 6 DAQ links fine, all 12
    # trigger links dead.
    _writes([(I2C_RST.addr, I2C_RST._reg_dir, I2C_RST._bit_inv),  # (0x21, 0x06, 0x8F)
             (I2C_RST.addr, I2C_RST._reg_out, I2C_RST._bit_pos)]) # (0x21, 0x02, 0x70)

    ### Multiplexer board ###
    #########################

    # The "Sgl" selection is left standing (closing it would spend another switch
    # toggle); the first data-path access re-selects via mux_select(), which we
    # force by forgetting the cached selection.
    mux_forget_selection()


def mux_setup(slot: str):
    """
    Power the hexaboard, its HGCROCs, and make sure the latter are out of their reset state:
    - Enable hexaboard power from the power management board (if any),
    - Enable the hexaboard's LDO regulators to power the HGCROCs,
    - Set the soft and hard HGCROCs reset pins to a HIGH state.

    Args:
        slot (str): Module multiplexer board slot ("A", "B", or "C")
    """
    # Retry the whole open->write->close sequence on a transient bus error, on a
    # fresh SMBus fd each attempt so a half-finished sequence always restarts
    # clean. The first TCAL6416 writes after a power cycle intermittently EIO at a
    # WANDERING point (the switch write one time, an expander register the next) --
    # the mark of a transient on this write-mostly PL master, not a dead device.
    # Without this a single EIO aborts server startup outright, which on the
    # Alabama bench was failing roughly half of all launches. Every write here is
    # an absolute value rather than a read-modify-write, so re-issuing the whole
    # sequence is idempotent. Mirrors mux_gpio.write() and enableROCs_alabama's _seq().
    attempts = 5
    for attempt in range(attempts):
        try:
            _mux_setup_once(slot)
            return
        except OSError as e:
            mux_forget_selection()
            if attempt == attempts - 1:
                raise
            print(f"IOError in mux_setup (attempt {attempt+1}/{attempts}): {e}. Retrying.")
            sleep(0.5 * (attempt + 1))
