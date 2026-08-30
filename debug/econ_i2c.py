#!/usr/bin/python3

import sys
#import click
import yaml
import numpy as np
import logging
import time

#FIXME
from hexactrl_io import Xil_i2c
from ECON import ECON

import timeit

fcmd_order = [
    "bcr",
    "ocr",
    "l1a",
    "nzs",
    "cal_pulse_int",
    "cal_pulse_ext",
    "ebr",
    "ecr",
    "link_reset_roc_t",
    "link_reset_roc_d",
    "link_reset_econ_t",
    "link_reset_econ_d",
    "spare0",
    "spare1",
    "spare2",
    "spare3",
    "spare4",
    "spare5",
    "spare6",
    "spare7",
    "unassigned",
    "fc_error",
]


class ECON_I2C:
    def __init__(
        self,
        bus_id,
        base,
        cfg_converter,
        logger_name=None,
        name="ECON",
        force_ones=None,
    ):
        # initialize bus (only Xilinx supported for now)
        i2c_bus = Xil_i2c(bus_id)

        #FIXME initialize ECON target
        #self.target = ECON(
        #    name=name,
        #    transport=i2c_bus,
        #    base_address=base,
        #    cfg_converter=cfg_converter,
        #    force_ones=force_ones,
        #)
        self.name = name
        self.logger = logging.getLogger(
            f"{__name__}_{logger_name}" if logger_name else __name__
        )

        # initialize config converter
        self.cfg = cfg_converter

    def set_base_address(self, new_base_address):
        self.target.set_base_address(new_base_address)

    def get_config(self, config_name=None, param_names=None):
        if config_name and param_names:
            self.logger.warning(
                "Both yaml configuration file and param_names are given, using configuration file"
            )

        if config_name:
            with open(config_name, "r") as f:
                config = yaml.safe_load(f)
        elif param_names:
            parameter_cfg = self.cfg.get_parameters_fromparamnames(param_names)
            config = self.cfg.get_cfg_fromnames(parameter_cfg)
        else:
            self.logger.error("No configuration file or parameter dictionary to write")
            return None
        self.logger.debug("Configuration to load %s" % config)
        return config

    def get_allregisters(self):
        """
        returns list of tuples (register_address, size_byte)
        for all possible register addresses
        """
        cfg = self.cfg.config[["address", "size_byte"]].sort_values(by="address")
        cfg["address"] = cfg["address"].apply(int, base=16)
        cfg_first = cfg.groupby("address").first().reset_index()
        cfg_list = list(zip(*map(cfg_first.get, ["address", "size_byte"])))
        return cfg_list

    def convert_read(self, readtable, read_str="Read", log=True):
        readparam = self.cfg.get_parameters_fromtable(readtable)
        self.logger.debug(f"{read_str} registers")
        if log:
            for parameter in sorted(readparam.keys()):
                parameter_value, parameter_access = readparam[parameter]
                if parameter_value == -1:
                    val = "NACK"
                else:
                    try:
                        val = f"0x{parameter_value:02x}"
                    except:
                        val = f'0x{int.from_bytes(parameter_value, "big"):02x}'
                self.logger.info(
                    "{access} {param}: {val}".format(
                        access=parameter_access.upper(),
                        param=parameter,
                        val=val,
                    )
                )

        # strip out access out of dictionary
        readparam = {reg: values[0] for reg, values in readparam.items()}
        return readparam

    def write_all(self, data):
        """
        data must be either a bytes object or a numpy array of dtype
        numpy.uint8. In either case, the length must be equal to
        self.cfg.total_length_bytes.
        """
        if isinstance(data, bytes):
            self.target.write_all(data)
        else:
            self.target.write_all(self.cfg.array_to_bytes(data))

    def read_all(self):
        """
        Read all of the I2C registers from start to finish and return a bytes
        object.
        """
        return self.target.read_all()

    def write(
        self, config=None, config_name=None, param_names=None, readback=True, log=True
    ):
        # NOTE: every write by default has a read
        if config is None:
            config = self.get_config(config_name, param_names)
            if param_names:
                self.logger.warning(
                    f"using econ_i2c.write with param_names is slow.  Instead of config_name={config_name} or param_names={param_names}, try using config={config}."
                )
        if config is None:
            self.logger.warning("No config to write")
            return None
        readtable = self.target.configure(config, readback)
        readparam = {}
        if readback:
            readparam = self.convert_read(readtable, read_str="Readback", log=log)
        return readparam

    def read(
        self,
        config=None,
        config_name=None,
        param_names=None,
        log=True,
        convert_read=False,
        minimal_convert_read=True,
        as_config=False,
    ):
        if config is None:
            config = self.get_config(config_name, param_names)
            self.logger.warning(
                f"using econ_i2c.read with param_names is slow.  Instead of config_name={config_name} or param_names={param_names}, try using config={config}."
            )
        r = self.target.read(config)
        if convert_read:
            self.logger.warning(
                f"using econ_i2c.read with convert_read=True is slow.  Instead of convert_read=True, try using convert_read=False and minimal_convert_read=True."
            )
            readparam = self.convert_read(r, log=log)
            return readparam
        elif minimal_convert_read:
            if log:
                for k, v in r:
                    self.logger.info(
                        "_".join(
                            [f"{ki:02d}" if isinstance(ki, int) else ki for ki in k]
                        )
                        + f": {v if isinstance(v,int) else int.from_bytes(v,'big'):02x}"
                    )
            return {
                "_".join([f"{ki:02d}" if isinstance(ki, int) else ki for ki in k]): v if isinstance(v,int) else int.from_bytes(v, "big")
                for k, v in r
            }
        elif as_config:
            return self.cfg.get_cfg_fromnames(self.convert_read(r, log=log))
        else:
            return r

    """
    The following are specific functions for ECON testing
    """

    def pllstatus_read(self, target, log=False):
        if target == "ECONTP1":
            status = self.read(
                config={
                    "ClocksAndResets": {
                        "Global": {
                            "pusm_state": None,
                        }
                    },
                    "Pll": {
                        "Global": {
                            "lf_locked": None,
                            "lf_loss_of_lock_count": None,
                            "vco_cap_select": None,
                        }
                    },
                },
                log=log,
            )
            pusm_state = status["ClocksAndResets_Global_pusm_state"]
            lol_count = status["Pll_Global_lf_loss_of_lock_count"]
            auto_lock = status["Pll_Global_lf_locked"]
            vco_capbank = status["Pll_Global_vco_cap_select"]
        else:
            status = self.read(
                config={
                    "ClocksAndResets": {
                        "Global": {
                            "pusm_state": None,
                            "lock_filter_locked": None,
                            "lock_filter_loss_of_lock_count": None,
                            "vco_capbank": None,
                        }
                    }
                },
                log=log,
            )
            pusm_state = status["ClocksAndResets_Global_pusm_state"]
            lol_count = status["ClocksAndResets_Global_lock_filter_loss_of_lock_count"]
            auto_lock = status["ClocksAndResets_Global_lock_filter_locked"]
            vco_capbank = status["ClocksAndResets_Global_vco_capbank"]

        return pusm_state, lol_count, auto_lock, vco_capbank

    def snapshot_i2c(self):
        """
        Configures manual i2c snapshot
        """
        self.logger.info("Configuring i2c manual snapshot")
        self.write(
            config={
                "Aligner": {
                    "Global": {
                        "i2c_snapshot_en": 1,
                        "snapshot_en": 1,
                        "snapshot_arm": 0,
                    }
                },
                "ChAligner": {
                    0: {"per_ch_align_en": 0},
                    1: {"per_ch_align_en": 0},
                    2: {"per_ch_align_en": 0},
                    3: {"per_ch_align_en": 0},
                    4: {"per_ch_align_en": 0},
                    5: {"per_ch_align_en": 0},
                    6: {"per_ch_align_en": 0},
                    7: {"per_ch_align_en": 0},
                    8: {"per_ch_align_en": 0},
                    9: {"per_ch_align_en": 0},
                    10: {"per_ch_align_en": 0},
                    11: {"per_ch_align_en": 0},
                },
            },
            log=False,
        )
        self.write(config={"Aligner": {"Global": {"snapshot_arm": 1}}}, log=True)
        self.snapshot_read()
        self.write(
            config={
                "Aligner": {"Global": {"snapshot_arm": 0, "i2c_snapshot_en": 0}},
                "ChAligner": {
                    0: {"per_ch_align_en": 0},
                    1: {"per_ch_align_en": 0},
                    2: {"per_ch_align_en": 0},
                    3: {"per_ch_align_en": 0},
                    4: {"per_ch_align_en": 0},
                    5: {"per_ch_align_en": 0},
                    6: {"per_ch_align_en": 0},
                    7: {"per_ch_align_en": 0},
                    8: {"per_ch_align_en": 0},
                    9: {"per_ch_align_en": 0},
                    10: {"per_ch_align_en": 0},
                    11: {"per_ch_align_en": 0},
                },
            },
            log=False,
        )

    def snapshot_read(self, print_snapshot=True):
        """
        Reads snapshot and related registers
        """
        readback = self.read(
            config={
                "ChAligner": {
                    i: {
                        "pattern_match": None,
                        "snapshot_dv": None,
                        "select": None,
                        "snapshot": None,
                    }
                    for i in range(12)
                }
            },
            log=False,
            convert_read=False,
            minimal_convert_read=True,
        )

        # read snapshot
        snapshots = np.array(
            [ readback[f"ChAligner_{link:02d}_snapshot"] for link in range(12) ],
            dtype=object,
        )
        snapshot_dvs = np.array(
            [readback[f"ChAligner_{link:02d}_snapshot_dv"] for link in range(12)]
        )
        pattern_matchs = np.array(
            [readback[f"ChAligner_{link:02d}_pattern_match"] for link in range(12)]
        )
        selects = np.array(
            [readback[f"ChAligner_{link:02d}_select"] for link in range(12)],
            dtype=object,
        )

        if print_snapshot:
            for link, s in enumerate(snapshots):
                self.logger.info(
                    f"   eRx {link:02d}: 0x{s:048x} snapshot_dv={snapshot_dvs[link]} pattern_match={pattern_matchs[link]} select=0x{selects[link]:02x}"
                )
        return snapshots, snapshot_dvs, pattern_matchs, selects

    def set_fcmdcapture(self, fcmd):
        self.logger.info(f"Set FCtrl_Global_capture_fcmd_ctrl to: {fcmd}")
        try:
            value_to_shift = fcmd_order.index(fcmd)
            value = 0x1 << value_to_shift
            self.logger.debug(f"Fast command index {value_to_shift} {value:02x}")
            self.write(
                param_names=(f"FCtrl_Global_capture_fcmd_ctrl:{value}",), log=True
            )
        except:
            self.logger.error(f"Fast command {fcmd} not in fcmd_order list")

    def read_fcmd(self, fcmd=None):
        if fcmd is None:
            fcmds = fcmd_order
        else:
            fcmds = [fcmd]
        for fcmd in fcmds:
            if "spare" in fcmd:
                to_read = f"FCtrl_Global_spare_fcmd_count_{fcmd[-1]}"
            else:
                to_read = f"FCtrl_Global_{fcmd}_fcmd_count"
            self.logger.debug(f"Reading {to_read}")
            self.read(param_names=(to_read,))

    def set_passthrough(self, passthrough: int = -1):
        """
        :param passthrough: Set pass-through mode (1), disable it (0) or read it (-1)
        :type passthrough: int
        """
        self.logger.debug(f"Setting passthrough to {passthrough}")
        if passthrough < 0:
            passthrough = None
        config = {"RocDaqCtrl": {"Global": {"pass_thru_mode": passthrough}}}
        if passthrough:
            self.write(config=config)
        else:
            self.read(config=config)

    def status_capture(self):
        """
        Sets the WO i2c status capture strobe bit
        """
        self.logger.debug(f"Doing i2c status capture")
        self.write(
            config={"RocDaqCtrl": {"Global": {"strobes_status_capture": {2: 1}}}},
            readback=False,
        )

    def status_clear(self):
        """
        Sets the WO i2c status clear strobe bit
        """
        self.logger.debug(f"Doing i2c status clear")
        self.write(
            config={"RocDaqCtrl": {"Global": {"strobes_status_clear": {0: 1}}}},
            readback=False,
        )

    def watchdog_capture(self):
        """
        Sets the WO i2c watchdog capture strobe bit
        """
        self.logger.debug(f"Doing i2c watchdog capture")
        self.write(config={"Watchdog": {"Global": {"capture": 1}}}, readback=False)

    def watchdog_capture_clear(self):
        """
        Sets the WO i2c status clear strobe bit
        """
        self.logger.debug(f"Doing i2c clear of the watchdog capture statuses")
        self.write(config={"Watchdog": {"Global": {"cap_clear": 1}}}, readback=False)

    def watchdog_request_clear(self):
        """
        Sets the WO i2c status clear strobe bit
        """
        self.logger.debug(f"Doing i2c clear of the watchdog alerts")
        self.write(config={"Watchdog": {"Global": {"req_clear": 1}}}, readback=False)

    def read_pusmstate(self, log=False):
        pusm_state_config = {"ClocksAndResets": {"Global": {"pusm_state": None}}}
        return self.read(pusm_state_config, log=log)["ClocksAndResets_Global_pusm_state"]

    def set_active_eTx(self, active_links):
        """
        Set number of active eTx
        :param active_links: list of active links (from 0 to nlinks)
        :type active_links: list
        """
        eTx_active = 0
        for i in active_links:
            eTx_active |= 1 << int(i)
        active_eTXs = {"FormatterBuffer": {"Global": {"active_etxs": eTx_active}}}
        self.write(config=active_eTXs)

    def read_active_eTx(self, target):
        etx_config = {"FormatterBuffer": {"Global": {"active_etxs": None}}}
        eTx_active = self.read(config=etx_config, log=False)[
            "FormatterBuffer_Global_active_etxs"
        ]
        if target == "ECONTP1":
            active_eTXs = np.array(
                [True if i < eTx_active else False for i in range(13)]
            )
        elif 'ECOND' in target:
            # NOTE: the reversed range to match the order of links in link capture
            active_eTXs = np.array(
                [(eTx_active >> i) & 1 for i in range(6)], dtype=bool
            )
        elif 'ECONT' in target:
            # NOTE: the reversed range to match the order of links in link capture
            active_eTXs = np.array(
                [(eTx_active >> i) & 1 for i in range(13)], dtype=bool
            )

        return active_eTXs

    def read_active_eRx(self):

        erx_config = {"ERx": {i: {"enable": None} for i in range(12)}}
        eRx_active = self.read(config=erx_config, log=False)

        active_eRXs = np.array(
            [eRx_active[f"ERx_{i:02d}_enable"] for i in range(12)], dtype=bool
        )
        return active_eRXs

    def train_channel(self):
        """
        Toggle train channel
        """
        self.write(config={"EprxGrpTop": {"Global": {"track_mode": 1}}}, readback=False, log=True)

        phase_select = self.read(
            config={
                "ChEprxGrp": {
                    f"{i:02d}": {"phase_select_channeloutput": None} for i in range(12)
                }
            },
            log=False,
        )
        initial_phase_select = list(phase_select.values())
        self.logger.info(f"ChEprxGrp phases before training: {initial_phase_select}")
        good = [False] * 12
        max_attempts = 1

        active_erx = self.read_active_eRx()

        for attempt in range(max_attempts):
            self.write(
                config={
                    "ChEprxGrp": {
                        channel: {"train_channel": 1}
                        for channel in range(12)
                        if not good[channel]
                    },
                },
                log=False,
                readback=False,
            )

            time.sleep(1e-2)
            self.write(
                config={
                    "ChEprxGrp": {
                        channel: {"train_channel": 0}
                        for channel in range(12)
                        if not good[channel]
                    },
                },
                log=False,
                readback=False,
            )

            time.sleep(1e-2)
            phase_select = self.read(
                config={
                    "ChEprxGrp": {
                        f"{i:02d}": {"phase_select_channeloutput": None}
                        for i in range(12)
                    }
                },
                log=False,
            )
            final_phase_select = list(phase_select.values())
            good = [
                final_phase_select[i] != 15 or active_erx[i] == 0 for i in range(12)
            ]
            if all(good):
                self.logger.info(
                    f"After Training ChEprxGrp phases {final_phase_select}"
                )
                self.logger.info(
                    f"Good channel phase select on all channels after roughly {attempt*2e-2} s"
                )
                break

        if not all(good):
            self.logger.warning(
                f"Failed to get good channel phase select after roughly {max_attempts*1e-3} s"
            )
        return final_phase_select, all(good)
