from level0.analyzer import *
from scipy.optimize import curve_fit
import glob
import seaborn as sns
sns.set_style("ticks")
from matplotlib.ticker import MultipleLocator
from enum import Enum


    
class SuccessCode(Enum):
    SUCCESS = 0
    ERROR_MULTIPLE_VALUES = 1
    ERROR_WRONG_VALUE = 2

class daq_tpg_checker_analyzer(analyzer):
    def encoder(self,number):
        if number > 15:
            suite =0
            cond=1
            n = 0
            binary_number = np.binary_repr(int(number), width =19)
            while(cond == 1):
                if str(binary_number)[n]=='1':
                    suite = binary_number[n+1:n+4]
                    cond = 0
                else:
                    n+=1
            encoded_sum = np.binary_repr(15-n,width=4)+str(suite)
            return encoded_sum
        else :
            pos = np.array([0,0,0,0])
            suite = np.binary_repr(int(number),width=4)[:-1]
            pos = np.hstack((pos,suite))
            concatenated_str = ''.join(pos)
            return str(concatenated_str)

    def check(self):

        config_file = self.odir+"/initial_full_config.yaml"
        with open(config_file, 'r') as cfile:
            yaml_data = yaml.safe_load(cfile)

        datatrig = self.data
       
        av_chans = np.array([np.arange(0,4),np.arange(4,8),np.arange(9,13),np.arange(13,17),np.arange(19,23),
                            np.arange(23,27),np.arange(28,32),np.arange(32,36),
                            np.arange(36,40),np.arange(40,44),np.arange(45,49),np.arange(49,53),
                            np.arange(55,59),np.arange(59,63),np.arange(64,68),np.arange(68,72),])
        errors = dict()
        errors['roc_s0']=dict()
        errors['roc_s1']=dict()
        errors['roc_s2']=dict()

        errors_enum = []

        for chip in datatrig.chip.unique():
            errors[f'roc_s{str(chip)}']['trig_cell'] = dict()
            for chanid in datatrig.channelsumid.unique():
                sel = datatrig['chip'] == chip
                sel &= datatrig['channelsumid'] == chanid
                channels = av_chans[chanid]
                extdata = np.zeros(4)
                for i in range(len(channels)):
                    extdata[i] = yaml_data['roc_s'+str(chip)]['sc']['ch'][channels[i]]['ExtData']
                sum = np.sum(extdata)
                rawsum = int(self.encoder(sum),2)
                trig_value = datatrig[sel].rawsum.unique() 
                if len(datatrig[sel].rawsum.unique()) >1:
                    errors_enum.append(SuccessCode.ERROR_MULTIPLE_VALUES)
                    errors[f'roc_s{str(chip)}']['trig_cell'][str(chanid)] = dict()
                    errors[f'roc_s{str(chip)}']['trig_cell'][str(chanid)]["Calculated"]= rawsum
                    errors[f'roc_s{str(chip)}']['trig_cell'][str(chanid)]["TriggerPath"] = trig_value.tolist()
                    errors[f'roc_s{str(chip)}']['trig_cell'][str(chanid)]["NumberOfWrong"] = len(np.where(datatrig[sel].rawsum != rawsum)[0])
                    
                else:
                    if datatrig[sel].rawsum.unique() != rawsum:
                        errors_enum.append(SuccessCode.ERROR_WRONG_VALUE)
                        errors[f'roc_s{str(chip)}']['trig_cell'][str(chanid)] = dict()
                        errors[f'roc_s{str(chip)}']['trig_cell'][str(chanid)]["TriggerPath"] = int(trig_value)
                        errors[f'roc_s{str(chip)}']['trig_cell'][str(chanid)]["Calculated"]= rawsum
                    else:
                        continue
        with open(self.odir+"/erreursdef2.yaml",'w') as fichier:
            yaml.dump(errors, fichier,default_flow_style=False)
        if len(errors_enum)==0:
            return [SuccessCode.SUCCESS]
        else:
            return errors_enum
        

        


if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        ped_analyzer = daq_tpg_checker_analyzer(indir, "unpacker_data/triggerhgcroc")
        ped_analyzer.mergeData()
        checker = ped_analyzer.check()
        print(checker)

    else:
        print("No argument given")
