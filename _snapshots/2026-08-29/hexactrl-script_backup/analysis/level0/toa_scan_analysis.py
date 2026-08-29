from level0.analyzer import *
from scipy.optimize import curve_fit
import glob
import numpy as np
import scipy.optimize
from nested_dict import nested_dict


class toa_scan_analyzer(analyzer):

    def erfunc(self,z,a,b):
    	return b*scipy.special.erfc(z-a)

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
        data = self.data[['chip','channel','channeltype','half','Toa_vref', 'toa_efficiency','toa_stdd','injectedChannels']].copy()
        toa_vrefs = data.Toa_vref.unique()
        inj_chan =data.injectedChannels.unique()

        for chip in range(nchip):
            fig, axs = plt.subplots(2,2,figsize=(15,10),sharey = False,constrained_layout = True)
            for chan in inj_chan:
                chans= [chan,chan+18,chan+36,chan+36+18]
                for ch in chans:
                    ax = axs[0,0] if ch < 36 else axs[0,1]
                    sel = data.chip == chip
                    sel &= data.channel == ch
                    sel &= data.channeltype == 0
                    sel &= data.injectedChannels == chan
                    df_sel = data[sel]
                    prof = df_sel.groupby("Toa_vref")["toa_efficiency"].sum()
                    try:
                        args = int(df_sel[df_sel.toa_efficiency < 0.2].groupby("Toa_vref")["toa_efficiency"].sum().index.min()) ## plus simple
                    except:
                        continue
                    ax.plot(df_sel.Toa_vref,df_sel.toa_efficiency,".-", label = "ch%i (%i)" %(ch,args))
                    ax.set_ylabel("toa eff")
                    ax.set_xlabel("Toa_vref")
                    ax.legend(ncol=3, loc = "lower right",fontsize=8)

                    ax = axs[1,0] if ch < 36 else axs[1,1]
                    ax.plot(df_sel.Toa_vref, df_sel.toa_stdd,".")
                    ax.set_ylabel("toa noise")
            plt.savefig("%s/1_toa_thr_chip%d_%s.png"%(self.odir,chip,suffix))
            

    def makePlot_trim(self):
        nchip = len( self.data.groupby('chip').nunique() )        
        data = self.data[['chip','channel','channeltype','half','trim_toa','toa_efficiency','injectedChannels']].copy()

        trim_toas = data.trim_toa.unique()
        inj_chan =data.injectedChannels.unique()
        for chip in range(nchip):
            fig, axs = plt.subplots(1,2, figsize=(15,8))
            for chan in inj_chan:
                chans= [chan,chan+18,chan+36, chan+36+18]
                for ch in chans:
                    ax = axs[0] if ch < 36 else axs[1]
                    sel = data.chip == chip
                    sel &= data.channel == ch
                    sel &= data.channeltype == 0
                    sel &= data.injectedChannels == chan
                    df_sel = data[sel]
                    prof = df_sel.groupby("trim_toa")["toa_efficiency"].sum()
                    try:
                        args = int(df_sel[df_sel.toa_efficiency < 0.2].groupby("trim_toa")["toa_efficiency"].sum().index.max()) ## plus simple
                    except:
                        args = 0
                    ax.plot(prof.index,prof.values,".-",label="ch%i (%i)" %(ch,args))
                    ax.set_ylabel("toa eff")
                    ax.set_xlabel("trim_toa")
                    ax.legend(ncol=3,loc="lower right",fontsize=10)
            plt.savefig("%s/trim_toa_thr_chip%d.png"%(self.odir,chip))

    def determineToa_vref(self):
        inj_chan =self.data.injectedChannels.unique()
        nchip = len( self.data.groupby('chip').nunique() )
        data = self.data[['chip','channel','channeltype','Toa_vref', 'toa_efficiency','injectedChannels']].copy()
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
                    chans= [chan,chan+18,chan+36,chan+36+18]
                    for ch in chans:
                        sel = data.chip == chip
                        sel &= data.channel == ch
                        sel &= data.channeltype == 0
                        sel &= data.injectedChannels == chan
                        sel &= data.toa_efficiency < 0.2
                        df_sel = data[sel]
                        prof = df_sel.groupby("Toa_vref")["toa_efficiency"].sum()
                        try:
                            args = int(prof.index.min())  ### PLUS SIMPLE !!!!!!!!!
                        except:
                            continue
                        if ch < 36:
                            mean_0.append(args)
                        else:
                            mean_1.append(args)
                mean = int(1.0*sum(mean_0)/len(mean_0))
                print("Toa_Vref for half0 is %i" %mean)
                nestedConf[chip_key_name]['sc']['ReferenceVoltage'][int(0)] = { 'Toa_vref' : mean }
                mean = int(1.0*sum(mean_1)/len(mean_1))
                print("Toa_Vref for half1 is %i" %mean)
                nestedConf[chip_key_name]['sc']['ReferenceVoltage'][int(1)] = { 'Toa_vref' : mean }
            else :
                print("WARNING : optimised Toa_vref will not be saved for ROC %d"%(chip))
        return nestedConf

    def determineToa_trim(self):
        inj_chan =self.data.injectedChannels.unique()
        nchip = len( self.data.groupby('chip').nunique() )
        data = self.data[['chip','channel','channeltype','injectedChannels','trim_toa', 'toa_efficiency']].copy()
        yaml_dict = {}
        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc')==0:
                    rockeys.append(key)
            rockeys.sort()

        trim_toas = data.trim_toa.unique()
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
                    chans= [chan,chan+18,chan+36, chan+36+18]    
                    for ch in chans:
                        sel = data.chip == chip
                        sel &= data.channel == ch
                        sel &= data.channeltype == 0
                        sel &= data.injectedChannels == chan
                        sel &= data.toa_efficiency < 0.2
                        df_sel = data[sel]
                        prof = df_sel.groupby("trim_toa")["toa_efficiency"].sum()
                        try:
                            alpha = int(prof.index.max()) ## plus simple
                        except:
                            alpha = 0
                        if alpha < 0:
                            alpha = 0
                        elif alpha > 63:
                            alpha = 63
                        print()
                        print(ch,alpha)
                        yaml_dict[chip_key_name]['sc']['ch'][int(ch)] = { 'trim_toa' : int( alpha ) }
            else :
                print("WARNING : optimised trim_toa will not be saved for ROC %d"%(chip))
        print(yaml_dict)
        with open(self.odir+'/trimmed_toa.yaml','w') as fout:
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
        toa_threshold_analyzer.makePlots()

    else:
        print("No argument given")
