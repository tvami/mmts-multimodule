from ROC import ROC
from Translator import Translator
from nested_dict import nested_dict
import ADCinterfaces

class CharBoard():
    """ Base class for characterization boards """

    def __init__(self, links, multimodule=False):
        self.multimodule = multimodule
        self.rocs = {name:ROC(link) for (name, link) in links.items()}
        self.writeCaches = {name:{} for name in links.keys()}  # dicts are thread-safe, so we can write to it from different threads
        for rname, roc in self.rocs.items(): 
            roc.reset()
            print('[%s] GPIO reset' % rname)
            
        roc_type = self.__detect_roc_type()         # Determine which ROC architecture we're on.
        self.translator = Translator(roc_type)      

    def configure(self, cfgs):
        """ Configure ROCs in separate threads and return after all are finished. """

        threads = []
        for lbl, cfg in cfgs.items():
            for rname in [name for name in self.rocs.keys() if lbl in name]:
                roc = self.rocs[rname]
                self.__write(roc, rname, cfg)
        #         thread = PropagatingThread(target=self.__write, args=(roc, rname, cfg))
        #         thread.start()
        #         threads.append(thread)
        # for thread in threads:
        #     try: 
        #         thread.join()                       # wait for threads to finish
        #     except Exception as e:                  # catch i2c exceptions.
        #         print("ERROR in configure: ", e)
        #         for rname, roc in self.rocs.items(): 
        #             print('[%s] GPIO reset' % rname)
        #             roc.reset()
        #         for lbl, roc in self.rocs.items(): 
        #             sortedPairs = self.translator.sort_pairs(self.writeCaches[lbl])
        #             roc.write(sortedPairs)                                                      # Rewrite caches
        #         return self.configure(cfgs)                                                     # Reload cfgs

        return "ROC(s) CONFIGURED"

    def read(self, cfgs=""):
        """ Factory method for unified interface to write. """

        if cfgs: return self.__read_fr_cfgs(cfgs)
        else: return self.__read_fr_cache()

    def reset_tdc(self):
        """ Reset MasterTDC parameter for all ROCs. """

        self.configure({lbl:{"MasterTdc":{"all":{"START_COUNTER":0}}} for lbl in self.rocs.keys()})
        self.configure({lbl:{"MasterTdc":{"all":{"START_COUNTER":1}}} for lbl in self.rocs.keys()})
        return "masterTDCs reset."

    def __write(self, roc, roc_name, cfg):
        """ Stuff that should run in a separate thread per ROC. """
        pairs = self.translator.pairs_from_cfg(cfg, self.writeCaches[roc_name], roc)
        self.writeCaches[roc_name].update(pairs)
        sortedPairs = self.translator.sort_pairs(pairs)
        roc.write(sortedPairs)
        print('[%s] Configured' % roc_name)

    def __read_fr_cache(self):
        """ Read addresses in write_param cache from rocs. """

        rd_cfgs = {}
        for lbl, roc in self.rocs.items():
            pairs = self.writeCaches[lbl]
            sortedPairs = self.translator.sort_pairs(pairs)
            rd_pairs = roc.read(sortedPairs)
            rd_cfg = self.translator.cfg_from_pairs(rd_pairs)
            rd_cfgs[lbl] = rd_cfg
        return rd_cfgs

    def __read_fr_cfgs(self, cfgs):
        """ Read addresses (=keys) in cfgs from rocs. """

        rd_cfgs = {}
        for lbl, cfg in cfgs.items():
            for roc_name in [name for name in self.rocs.keys() if lbl in name]:
                roc = self.rocs[roc_name]
                req_keys = set(key[-1] for key in nested_dict(cfg).keys_flat())
                pairs = self.translator.pairs_from_cfg(cfg, self.writeCaches[roc_name],roc)
                sortedPairs = self.translator.sort_pairs(pairs)
                rd_pairs = roc.read(sortedPairs)
                rd_cfg = self.translator.cfg_from_pairs(rd_pairs)	# params in same reg are also read..
                req_cfg = nested_dict()		                        # .. so only return requested config.
                for idx, val in nested_dict(rd_cfg).items_flat():
                    if idx[-1] in req_keys: 	                    # idx=(block,blockID,param)
                        req_cfg[idx[0]][idx[1]][idx[2]] = val
                rd_cfgs[roc_name] = req_cfg.to_dict()
        return rd_cfgs

    def __detect_roc_type(self):
        """ Query ROCs to detect if we're on Si or SiPM. """
    
        regs = [
                [{(32,37):  None}],
                [{(224,10):  None}],
                [{(237,10):  None}]]
        valMap = {
            "Si"     : [130,0,0],
            "SiPM"   : [143,0,0],
            "Siv3"   : [0,125,0],
            "SiPMv3" : [0,207,0],
            "Siv3b"  : [0,125,104],
            "SiPMv3b": [0,207,104],
        }
        roc = next(iter(self.rocs.values()))
        readBack = list( roc.read(regs).values() )

        try:
            [roc_type] = list(filter(lambda x: valMap[x] == readBack, valMap))
            print(f'Identify a board with HGCROC {roc_type}')
        except Exception as e:
            print(f'{e}. Could not find expected read back values when trying to identify the ROC type')
            print(f'  readBack = {readBack} (expected {valMap["Siv3b"]} for a V3 LD Full HB)')
            roc_type="Siv3"
        return roc_type
    
class HexaBoard(CharBoard):
    """
    HexaBoard differs from CharBoard by:
    1. Board Orientation (alignment of Trophy i2c labels with ROC addresses found on bus)
    2. On-board Trophy ADCs
    """
    def __init__(self, links, multimodule=False):
        super().__init__(links, multimodule)
        self.adc_pwr = {}
        
    def read_pwr(self):
        """ Return reading of TrophyBoard's analog (piv_a) and digital (piv_d) ADCs. """
        return self.ADCinterface.read_pwr()

    def initialize_adc(self, cfgs):
        """
        The interface required to readout the ADC chip depends on the version of the Trophy board.
        This function instantiate and initialize the proper interface.
        """

        if cfgs["Trophy_version"]=="TrophyV2":
            self.ADCinterface = ADCinterfaces.ADCTrophyV2()
        elif cfgs["Trophy_version"]=="TrophyV3":
            self.ADCinterface = ADCinterfaces.ADC1TrophyV3(cfgs)
            self.RTD = ADCinterfaces.RTD_TrophyV3(cfgs)
        else:
            raise KeyError("ADC_version %s is not supported"%cfgs["Trophy_version"])
        return "Interface to ADC chip initialized"
        
    def calib_adc_offset(self, cfgs):
        return self.ADCinterface.meas_adc_offset(cfgs)

    def read_adc(self, cfgs):
        return self.ADCinterface.read_adc(cfgs)

    def meas_adc_temp(self,cfgs):
        try:
            return self.RTD.meas_adc_temp(cfgs)
        except:
            raise KeyError("Temperature measurement is only implemented for the TrophyV3")
        
    def meas_rtd_temp(self,cfgs):
        try:
            return self.RTD.meas_rtd_temp(cfgs)
        except:
            raise KeyError("Temperature measurement is only implemented for the TrophyV3")
