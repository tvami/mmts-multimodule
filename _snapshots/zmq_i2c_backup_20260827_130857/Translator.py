import functools
from itertools import groupby, count
from operator import itemgetter
from nested_dict import nested_dict
import pickle
import math
import os

def memoize(fn):
    """ Readable memoize decorator. """

    fn.cache = {}
    @functools.wraps(fn)
    def inner(inst, *key):
        if key not in fn.cache:
            fn.cache[key] = fn(inst, *key)
        return fn.cache[key]
    return inner

class Translator():
    """ Translate between (human-readable) config and corresponding address/register values. """

    regmap_dict = {
        "Si":      "./reg_maps/HGCROCv2_I2C_params_regmap_dict.pickle",
        "SiPM":    "./reg_maps/HGCROCv2_sipm_I2C_params_regmap_dict.pickle",
        "Siv3":    "./reg_maps/HGCROC3_I2C_params_regmap_dict.pickle",
        "SiPMv3":  "./reg_maps/HGCROC3_sipm_I2C_params_regmap_dict.pickle",
        "Siv3b":   "./reg_maps/HGCROC3b_I2C_params_regmap_dict.pickle",
        "SiPMv3b": "./reg_maps/HGCROC3b_sipm_I2C_params_regmap_dict.pickle"
    }
    
    def __init__(self, roc_type):
        try:
            self.paramMap = self.__load_param_map(self.regmap_dict[roc_type])
        except Exception as e:
            print("Specified ROC type unknown.")
            raise # re-raise to fail early and not silence the exception in the traceback

    def cfg_from_pairs(self, pairs):
        """
        Convert from {addr:val} pairs to {param:param_val} config.
        We can only recover a parameter from a pair when it is in the common cache.
        However, when we read (or write) a param the common cache is populated in advance.
        """

        cfg = nested_dict()
        for param, param_regs in self.__regs_from_paramMap.cache.items():
            for reg_id, reg in param_regs.items():
                addr = (reg["R0"], reg["R1"])
                if addr in pairs.keys():
                    prev_regVal = cfg[param[0]][param[1]][param[2]] if cfg[param[0]][param[1]][param[2]]!={} else 0
                    paramVal = self.__paramVal_from_regVal(reg, pairs[addr], prev_regVal)
                    cfg[param[0]][param[1]][param[2]] = paramVal
        return cfg.to_dict()

    def pairs_from_cfg(self, cfg, writeCache, roc):
        """
        Convert an input config dict to addr (R0,R1): value (R2) pairs.
        There is two cases to consider for setting parameter value information:
        Case 1: One parameter value spans several registers. (Ex. IdleFrame)
        Case 2: Several parameter values share same register. (Ex. Delay9, Delay87)
        """

        cfg = self.__cut_sc(cfg)
        pairs = {}
        for block in cfg:
            for blockId in cfg[block]:
                for param, paramVal in cfg[block][blockId].items():
                    if not isinstance(blockId, int):
                        if blockId == "all":
                            blockIds = [key for key,val in self.paramMap[block].items()]
                        elif "," in blockId:
                            blockIds = [int(bid) for bid in blockId.split(",")]
                        elif "-" in blockId:
                            limits = [int(bid) for bid in blockId.split("-")]
                            blockIds = range(limits[0], limits[1]+1)
                    else: blockIds = [blockId]

                    for Id in blockIds:
                        par_regs = self.__regs_from_paramMap(block, Id, param)
                        for reg_id, reg in par_regs.items():
                            addr = (reg["R0"], reg["R1"])
                            if addr in pairs: prev_paramVal = pairs[addr]                          # regVal already added
                            elif addr in writeCache: prev_paramVal = writeCache[addr]              # regVal already cached/written
                            else: prev_paramVal = list(roc.read([[{addr:0}]]).values())[0]
                            pairs[addr] = self.__regVal_from_paramVal(reg, paramVal, prev_paramVal)
        return pairs

    def expand_cfgs(self, cfgs, rocs):
        """ Expand ROC names & halves (if appropriate) """

        res = nested_dict()
        for lbl, cfg in cfgs.items():
            cfg = self.__cut_sc(cfg)
            for nlbl in [name for name in rocs if lbl in name]:
                for blk, blk_cfg in cfg.items():
                    for half, half_cfg in blk_cfg.items():
                        if half=='all':
                            res[nlbl][blk][0] = cfgs[lbl][blk]['all']
                            res[nlbl][blk][1] = cfgs[lbl][blk]['all']
                        else:
                            res[nlbl][blk] = cfgs[lbl][blk]
        return res.to_dict()

    def sort_pairs(self, pairs):
        """ Sort pairs by same R0 and consecutive R1 """

        addrs = pairs.keys()
        addrs = sorted(addrs, key=itemgetter(0))
        addrs = sorted(addrs, key=itemgetter(1))
        sortedAddrs = [list(g) for k, g in groupby(addrs, key=lambda addr, c=count(): complex(addr[0]-next(c), addr[1]))]
        sortedPairs = [[{addr: pairs[addr]} for addr in subList] for subList in sortedAddrs]
        return sortedPairs

    @memoize
    def __regs_from_paramMap(self, block, blockId, name):
        """ (block, blockId, name) -> (R0, R1, defval_mask, param_mask, param_minbit, reg_mask, reg_id) """

        return self.paramMap[block][blockId][name]

    def __load_param_map(self, fname):
        """ Load a pickled register map into cache (as a dict). """

        # Resolve reg_maps paths relative to THIS file, not the caller's cwd, so
        # zmq_server can be launched from anywhere (e.g. ~/multimodule).
        if not os.path.isabs(fname):
            fname = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        with open(fname, 'rb') as handle:
            paramMap = pickle.load(handle)
        return paramMap

    def __regVal_from_paramVal(self, reg, param_value, prev_param_value=0):
        """ Convert parameter value (from config) into register value (1 byte). """

        reg_value = param_value & reg["param_mask"]
        reg_value >>= self.__get_lsb_id(reg["param_mask"])
        reg_value <<= self.__get_lsb_id(reg["reg_mask"])
        inv_mask = 0xff - reg["reg_mask"]
        reg_value = (prev_param_value & inv_mask) + reg_value
        return reg_value

    def __paramVal_from_regVal(self, reg, reg_value, prev_reg_value=0):
        """ Convert register value into (part of) parameter value. """

        param_val = reg_value & reg["reg_mask"]
        param_val >>= self.__get_lsb_id(reg["reg_mask"])
        param_val <<= self.__get_lsb_id(reg["param_mask"]) 
        param_val += prev_reg_value
        return param_val

    def __get_lsb_id(self, byte):
        """ Return position of least significant bit of byte. """

        return int(math.log(byte & -byte)/math.log(2))

    def __cut_sc(self, cfg):
        """ Allow to get rid of 'sc' inside config yaml. """

        return cfg['sc'] if 'sc' in cfg.keys() else cfg
