from level0.analyzer import *
from scipy.optimize import curve_fit
import glob
import numpy as np
import scipy.optimize
from nested_dict import nested_dict


class tot_scan_analyzer(analyzer):

    def erfunc(self,z,a,b):
    	return b*scipy.special.erfc(a-z)

    def fit(self,x,y,p):
        try:
            args, cov = scipy.optimize.curve_fit(self.erfunc,x,y,p0=p)
            return args
        except:
            print("Fit cannot be found")
            return p

    def erfunc_trim(self,z,a,b):
        return b*scipy.special.erfc(a-z)

    def fit_trim(self,x,y,p):
        try:
            args, cov = scipy.optimize.curve_fit(self.erfunc_trim,x,y,p0 = p)
            return args
        except:
            print("Fit cannot be found")
            return p

    def makePlot(self,suffix=""):
        nchip = len( self.data.groupby('chip').nunique() )        
        data = self.data[['chip','channel', 'half','Tot_vref', 'tot','injectedChannels']].copy()
        tot_vrefs = data.Tot_vref.unique()
        inj_chan =data.injectedChannels.unique()

        for chip in range(nchip):
            fig, axs = plt.subplots(1,2,figsize=(15,10),sharey = False,constrained_layout = True)
            for chan in inj_chan:
                chans= [chan,chan+18]
                for ch in chans:
                    for half in range(2):
                        ax = axs[half]
                        sel = data.chip == chip
                        sel &= data.channel == ch
                        sel &= data.half == half
                        sel &= data.injectedChannels == chan
                        df_sel = data[sel]
                        prof = df_sel.groupby("Tot_vref")["tot"].median()
                        try:
                            args = prof.index[np.argmin(prof.values)]
                        except:
                            continue
                        ax.plot(prof.index,prof.values,".-", label = "ch%i (%i)" %(ch,args))
                        ax.set_ylabel("tot eff")
                        ax.set_xlabel("Tot_vref")
                        ax.legend(ncol=3, loc = "lower right",fontsize=8)
                            
            plt.savefig("%s/1_tot_thr_chip%d_%s.png"%(self.odir,chip,suffix))


    def makePlot_trim(self):
        nchip = len( self.data.groupby('chip').nunique() )        
        data = self.data[['chip','channel', 'half','trim_tot','tot','injectedChannels']].copy()
        trim_tots = data.trim_tot.unique()
        inj_chan =data.injectedChannels.unique()
        for chip in range(nchip):
            fig, axs = plt.subplots(1,2, figsize=(15,8))
            for chan in inj_chan:
                chans= [chan,chan+18]
                for ch in chans:
                    for half in range(2):
                        ax = axs[half]
                        sel = data.chip == chip
                        sel &= data.channel == ch
                        sel &= data.half == half
                        sel &= data.injectedChannels == chan
                        df_sel = data[sel]
                        prof = df_sel.groupby("trim_tot")["tot"].median()
                        try:
                            args = prof.index[np.max(np.where(prof.values==0))]
                        except:
                            args = 0
                        ax.plot(prof.index,prof.values,".-",label="ch%i (%i)" %(ch,args))
                        ax.set_ylabel("tot eff")
                        ax.set_xlabel("trim_tot")
                        ax.legend(ncol=3,loc="lower right",fontsize=10)
            plt.savefig("%s/trim_tot_thr_chip%d.png"%(self.odir,chip))


    def determineTot_vref(self):
        inj_chan =self.data.injectedChannels.unique()
        nchip = len( self.data.groupby('chip').nunique() )
        data = self.data[['chip','channel', 'half', 'Tot_vref', 'tot','injectedChannels']].copy()
        nestedConf = nested_dict()
        
        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc')==0:
                    rockeys.append(key)
            rockeys.sort()
 
        for chip in range(nchip):
            if chip<len(rockeys):
                chip_key_name = rockeys[chip]
                mean_0 = []
                mean_1 = []
                for chan in inj_chan:
                    chans= [chan,chan+18]
                    for ch in chans:
                        for half in range(2):
                            sel = data.chip == chip
                            sel &= data.channel == ch
                            sel &= data.half == half
                            sel &= data.injectedChannels == chan
                            df_sel = data[sel]
                            prof = df_sel.groupby("Tot_vref")["tot"].median()
                            try:
                                args = prof.index[np.argmin(prof.values)]
                            except:
                                continue
                            if half == 0:
                                mean_0.append(args)
                            else:
                                mean_1.append(args)
                mean = int(1.0*sum(mean_0)/len(mean_0))
                print("Tot_Vref for half0 is %i" %mean)
                nestedConf[chip_key_name]['sc']['ReferenceVoltage'][int(0)] = { 'Tot_vref' : mean }
                mean = int(1.0*sum(mean_1)/len(mean_1))
                print("Tot_Vref for half1 is %i" %mean)
                nestedConf[chip_key_name]['sc']['ReferenceVoltage'][int(1)] = { 'Tot_vref' : mean }
            else :
                print("WARNING : optimised Tot_vref will not be saved for ROC %d"%(chip))
        return nestedConf

    def determineTot_trim(self):
        inj_chan =self.data.injectedChannels.unique()
        nchip = len( self.data.groupby('chip').nunique() )
        data = self.data[['chip','channel', 'half', 'injectedChannels','trim_tot', 'tot']].copy()
        yaml_dict = {}
        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc')==0:
                    rockeys.append(key)
            rockeys.sort()

        trim_tots = data.trim_tot.unique()
        for chip in range(nchip):
            if chip<len(rockeys):
                chip_key_name = rockeys[chip]
                yaml_dict[chip_key_name] = {
                'sc' : {
                'ch' : { 
                }
                }
                }
                for chan in inj_chan:
                    chans= [chan,chan+18]    
                    for ch in chans:
                        for half in range(2):
                            sel = data.chip == chip
                            sel &= data.channel == ch
                            sel &= data.half == half
                            sel &= data.injectedChannels == chan
                            df_sel = data[sel]
                            prof = df_sel.groupby("trim_tot")["tot"].median()
                            try:
                                alpha = prof.index[np.max(np.where(prof.values==0))]
                            except:
                                alpha = 0
                            if alpha < 0:
                                alpha = 0
                            elif alpha > 63:
                                alpha = 63
                            print()
                            print(ch,alpha)
                            yaml_dict[chip_key_name]['sc']['ch'][int(ch+36*half)] = { 'trim_tot' : int( alpha ) }
            else :
                print("WARNING : optimised trim_tot will not be saved for ROC %d"%(chip))
        print(yaml_dict)
        with open(self.odir+'/trimmed_tot.yaml','w') as fout:
                yaml.dump(yaml_dict,fout)

        return yaml_dict




if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        toa_threshold_analyzer = toa_threshold_scan_analyzer(odir=odir)
        files = glob.glob(indir+"/toa_threshold_scan*.root")
        print(files)

        for f in files:
            toa_threshold_analyzer.add(f)

        toa_threshold_analyzer.mergeData()
        #toa_threshold_analyzer.determine_bestToa_vref()
        toa_threshold_analyzer.makePlots()

    else:
        print("No argument given")
