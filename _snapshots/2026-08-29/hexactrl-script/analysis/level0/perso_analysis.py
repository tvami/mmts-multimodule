from level0.analyzer import *
import glob
import scipy.optimize 
from nested_dict import nested_dict

class data_analyzer(analyzer):

    def raw_reader(self,f,injectedChannel,gain):
        if gain == 1:
            capa = 10000
        else:
            capa = 500
        r_summary = reader(f)
        r_raw = rawroot_reader(f)
        r_raw.df['Calib_dac'] = r_summary.df.Calib_dac.unique()[0]
        r_raw.df['injectedChannel'] = injectedChannel            
        r_raw.df['q'] = (r_raw.df['Calib_dac'] / 4096 + 0.002) * capa
        self.dataFrames.append(r_raw.df)

    def reglinear(self,z,a,b):
        return a*z + b

    def fit(self,x,y,p):
        try:
            args, cov = scipy.optimize.curve_fit(self.reglinear,x,y,p0 = p)
            return args
        except:
            print("Fit cannot be found")
            return p

    def toa_rms_profile(self,z,a,b):
        res = (a/z)**2 + b**2
        return (res)**(0.5)

    def fit_toa_resolution(self,x,y,p):
        try:
            args, cov = scipy.optimize.curve_fit(self.toa_rms_profile,x,y,p0 = p)
            return args
        except:
            print("Fit cannot be found")
            return [-100,-100]
    
    def toa_tw_profile(self,z,a,b):
        res = a/z + b
        return res

    def fit_toa_tw(self,x,y,p):
        try:
            args, cov = scipy.optimize.curve_fit(self.toa_tw_profile,x,y,p0 = p)
            return args
        except:
            print("Fit cannot be found")
            return [-100,-100]
    
    def determineCalibDacMax(self,data,*args):
        data["residu"] = data["adc_mean"] - self.reglinear(data["Calib_dac"],*args)
        df_ = data[abs(data.residu) < 5]
        max_calib = df_.Calib_dac.max()
        return max_calib

    def determineCalibDacMax_raw(self,data,*args):
        data["residu"] = data["adc"] - self.reglinear(data["Calib_dac"],*args)
        df_ = data[abs(data.residu) < 5]
        max_calib = df_.Calib_dac.max()
        return max_calib

    def determineAdcRange(self):
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','half','channel','channeltype','Calib_dac','adc_mean','tot_median']].copy()
        sel_data = sel_data.sort_values(by=['Calib_dac'],ignore_index=True)
        max_dict = {}
        for chip in range(nchip):
            sel = sel_data.adc_mean > 500
            nhits = sel_data[sel].groupby(["channel"]).size()
            chans = nhits.index.values
            for ch in chans:
                sel = sel_data.chip == chip
                sel &= sel_data.channel == ch
                df_full = sel_data[sel].copy()
                sel &= sel_data.Calib_dac < 500
                sel &= sel_data.tot_median == 0
                df_sel = sel_data[sel].copy()
                prof = df_full.groupby("Calib_dac")["adc_mean"].mean()
                args = self.fit(df_sel.Calib_dac,df_sel.adc_mean,p=[0,0])
                max_calib = self.determineCalibDacMax(df_full,*args)
                max_dict[ch]=max_calib
        return max_dict


    def determineAdcRange_raw(self):
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','half','channel','Calib_dac','adc','tot']].copy()
        sel_data = sel_data.sort_values(by=['Calib_dac'],ignore_index=True)
        max_dict = {}
        for chip in range(nchip):
            sel = sel_data.adc > 500
            nhits = sel_data[sel].groupby(["channel"]).size()
            chans = nhits.index.values
            for ch in chans:
                sel = sel_data.chip == chip
                sel &= sel_data.channel == ch
                df_full = sel_data[sel].copy()
                sel &= sel_data.Calib_dac < 500
                sel &= sel_data.tot == 0
                df_sel = sel_data[sel].copy()
                prof = df_full.groupby("Calib_dac")["adc"].mean()
                args = self.fit(df_sel.Calib_dac,df_sel.adc,p=[0,0])
                max_calib = self.determineCalibDacMax_raw(df_full,*args)
                max_dict[ch]=max_calib
        return max_dict


    def makePlots(self,fig,nestedConf):
        df = self.data
        chips = df.chip.unique()
        halfs = df.half.unique()
        Calib_dacs = df.Calib_dac.unique()
        sel = df.adc > 500
        nhits = df[sel].groupby(["channel"]).size()
        chans = nhits.index.values
        chan = int(df.injectedChannel.unique()[0])
        chans = [chan, chan+18]
        print("#############  channels  ##################")
        print(chans)
        colors_0 = plt.cm.viridis_r(np.linspace(0,1,len(range(36))))
        colors_1 = plt.cm.inferno(np.linspace(0,1,len(range(36))))
        colors_2 = plt.cm.cividis(np.linspace(0,1,len(range(36))))
        axs = fig.axes

        for chip in chips:
            if chip == 0:
                colors = colors_0
            elif chip == 1:
                colors = colors_1
            else:
                colors = colors_2
            for ch in chans:
                for half in range(2):
                    ax = axs[half]
                    sel = df.chip == chip
                    sel &= df.channel == ch
                    sel &= df.half == half
                    sel &= df.tot ==0  ########################
                    df_full = df[sel]
                    sel &= df.adc < 700
                    sel &= df.tot ==0
                    df_sel = df[sel]
                    prof = df_sel.groupby("q")["adc"].mean()
                    prof_noise = df_full.groupby("q")["adc"].std()
                    prof_full = df_full.groupby("q")["adc"].mean()
                    #if prof_noise.values.max() > 100:
                    #    continue
                    args = self.fit(prof.index,prof.values,p=[1.31,30])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['adc_slope'] = float(args[0])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['adc_intercept'] = float(args[1])
                    ax.plot(prof_full.index,prof_full.values,"-", color=colors[ch],\
                            label = "ch%i" %(ch))
                    #ax.plot(df_full.q,self.reglinear(df_full.q,*args),"--", color="k")
                    ax.set_ylabel("adc")
                    ax.set_xlabel('charge [fC]')
                    ax.legend(ncol=2, loc = "lower right",fontsize=8)
                    ax.set_ylim(0,1000)

                    ax = axs[half+2] 
                    ax.plot(prof_noise.index, prof_noise.values,"-",color=colors[ch])
                    ax.set_ylabel("adc noise")
                    ax.set_xlabel('charge [fC]')
                    ax.set_ylim(-1,5)

        return nestedConf


    def makeResiduPlots(self,fig):
        df = self.data
        chips = df.chip.unique()
        halfs = df.half.unique()
        Calib_dacs = df.Calib_dac.unique()
        sel = df.adc > 500
        nhits = df[sel].groupby(["channel"]).size()
        chans = nhits.index.values
        chan = int(df.injectedChannel.unique()[0])
        chans = [chan, chan+18]
        colors_0 = plt.cm.viridis_r(np.linspace(0,1,len(range(36))))
        colors_1 = plt.cm.inferno(np.linspace(0,1,len(range(36))))
        colors_2 = plt.cm.cividis(np.linspace(0,1,len(range(36))))
        axs = fig.axes

        for chip in chips:
            if chip == 0:
                colors = colors_0
            elif chip == 1:
                colors = colors_1
            else:
                colors = colors_2
            for ch in chans:
                for half in range(2):
                    ax = axs[half]
                    sel = df.chip == chip
                    sel &= df.channel == ch
                    sel &= df.half == half
                    df_noise = df[sel]
                    sel &= df.tot ==0
                    df_full = df[sel]
                    sel &= df.adc < 700
                    df_sel = df[sel]
                    prof = df_sel.groupby("q")["adc"].mean()
                    prof_noise = df_noise.groupby("q")["adc"].std()
                    prof_full = df_full.groupby("q")["adc"].mean()
                    #if prof_noise.values.max() > 100:
                    #    continue
                    args = self.fit(prof.index,prof.values,p=[1.31,30])
                    ax.plot(prof_full.index,prof_full.values,"-", color=colors[ch],\
                            label = "ch%i" %(ch))
                    ax.set_ylabel("adc")
                    ax.set_xlabel('charge [fC]')
                    ax.legend(ncol=2, loc = "lower right",fontsize=8)
                    ax.set_ylim(0,1000)

                    ax = axs[half+2] 
                    ax.plot(prof_full.index,(prof_full.values - self.reglinear(prof_full.index,*args))/10,"-", color=colors[ch])
                    ax.set_ylabel("INL [%]")
                    ax.set_xlabel('charge [fC]')
                    ax.set_ylim(-2,2)

        return 

    def makeToaPlots(self,fig,nestedConf):
        target = 5
        lsb = 25
        df = self.data
        chips = df.chip.unique()
        halfs = df.half.unique()
        Calib_dacs = df.Calib_dac.unique()
        sel = df.adc > 500
        nhits = df[sel].groupby(["channel"]).size()
        chans = nhits.index.values
        chan = int(df.injectedChannel.unique()[0])
        chans = [chan, chan+18]
        colors_0 = plt.cm.viridis_r(np.linspace(0,1,len(range(36))))
        colors_1 = plt.cm.inferno(np.linspace(0,1,len(range(36))))
        colors_2 = plt.cm.cividis(np.linspace(0,1,len(range(36))))
        axs = fig.axes

        for chip in chips:
            if chip == 0:
                colors = colors_0
            elif chip == 1:
                colors = colors_1
            else:
                colors = colors_2
            for ch in chans[:]:
                for half in range(2):
                    ax = axs[half]
                    sel = df.chip == chip
                    sel &= df.channel == ch
                    sel &= df.half == half
                    sel &= df.toa > 0
                    df_sel = df[sel]
                    toa_vs_calib = df_sel.groupby("q")["toa"]
                    pk_pk = toa_vs_calib.apply(max) - toa_vs_calib.apply(min) + 1 
                    pk_pk -= toa_vs_calib.nunique()
                    mask_outliers = pk_pk[pk_pk.values < target]
                    sel &= df.q.isin(mask_outliers.index.values)
                    df_full = df[sel]
                    prof_sel = df_sel.groupby("q")["toa"].mean()
                    prof = df_full.groupby("q")["toa"].mean()
                    args = self.fit_toa_tw(prof.index,prof.values*lsb/1000,p=[2,9])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['tw_fit'] = float(args[0])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['tw_floor'] = float(args[1])
                    ax.plot(df_sel.q, df_sel.toa*lsb/1000 - prof.values.min()*lsb/1000 + 0.1,'.',color=colors[ch],\
                            label="ch%i" %(ch))
                    ax.plot(prof.index,self.toa_tw_profile(prof.index,*args) - prof.values.min()*lsb/1000 + 0.1,"--",color="k")
                    ax.legend(title=r'fit: $a/Q + b$',ncol=2, loc = "upper right",fontsize=8)
                    ax.set_ylabel("toa [ns]")
                    ax.set_xlabel('charge [fC]')

                    ax = axs[half+2] 
                    prof_noise = df_full.groupby("q")["toa"].std()
                    args = self.fit_toa_resolution(prof_noise.index,prof_noise.values*lsb,p=[2000,25])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['TimeResolution_fit'] = float(args[0])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['TimeResolution_floor'] = float(args[1])
                    ax.plot(prof_noise.index, prof_noise.values*lsb,"-",color=colors[ch],\
                            label="ch%i" %(ch))
                    ax.plot(prof_noise.index,self.toa_rms_profile(prof_noise.index,*args),"--",color="k")
                    ax.legend(title = r'fit: $sqrt((a/Q)² + b²)$',ncol=2, loc = "upper right",fontsize=8)
                    ax.set_ylabel("toa noise [ps]")
                    ax.set_xlabel("charge [fC]")

        return nestedConf
        


    def makeTotPlots(self,fig):
        target = 20
        df = self.data
        chips = df.chip.unique()
        halfs = df.half.unique()
        Calib_dacs = df.Calib_dac.unique()
        sel = df.adc > 500
        nhits = df[sel].groupby(["channel"]).size()
        chans = nhits.index.values
        chan = int(df.injectedChannel.unique()[0])
        chans = [chan, chan+18]
        #chans = [chan]
        colors_0 = plt.cm.viridis_r(np.linspace(0,1,len(range(36))))
        colors_1 = plt.cm.inferno(np.linspace(0,1,len(range(36))))
        colors_2 = plt.cm.cividis(np.linspace(0,1,len(range(36))))
        axs = fig.axes

        for chip in chips:
            if chip == 0:
                colors = colors_0
            elif chip == 1:
                colors = colors_1
            else:
                colors = colors_2
            for ch in chans:
                for half in range(2):
                    ax = axs[half]
                    sel = df.chip == chip
                    sel &= df.channel == ch
                    sel &= df.half == half
                    sel &= df.tot > 0
                    df_sel = df[sel]
                    tot_vs_calib = df_sel.groupby("q")["tot"]
                    pk_pk = tot_vs_calib.apply(max) - tot_vs_calib.apply(min) + 1 
                    pk_pk -= tot_vs_calib.nunique()
                    mask_outliers = pk_pk[pk_pk.values < target]
                    sel &= df.Calib_dac.isin(mask_outliers.index.values)
                    df_full = df[sel]
                    prof = df_full.groupby("q")["tot"].mean()
                    ax.plot(prof.index/1000, prof.values * 0.05,'-',color=colors[ch],label="ch%i" %ch)
                    #ax.plot(df_full.q / 1000, df_full.tot * 0.05, '.', color=colors[ch],label="ch%i" %ch)
                    ax.legend(ncol=2, loc = "lower right",fontsize=8)
                    ax.set_ylabel("tot [ns]")
                    ax.set_xlabel("charge [pC]")

                    ax = axs[half+2] 
                    prof_noise = df_full.groupby("q")["tot"].std()
                    ax.plot(prof_noise.index/1000, prof_noise.values * 50,"-",color=colors[ch])
                    ax.set_ylabel("tot noise [ps]")
                    ax.set_xlabel("charge [pC]")

        return 

    def makeResiduTotPlots(self,fig,nestedConf):
        target = 5
        df = self.data
        chips = df.chip.unique()
        halfs = df.half.unique()
        Calib_dacs = df.Calib_dac.unique()
        sel = df.adc > 500
        nhits = df[sel].groupby(["channel"]).size()
        chans = nhits.index.values
        chan = int(df.injectedChannel.unique()[0])
        chans = [chan, chan+18]
        #chans = [chan]
        colors_0 = plt.cm.viridis_r(np.linspace(0,1,len(range(36))))
        colors_1 = plt.cm.inferno(np.linspace(0,1,len(range(36))))
        colors_2 = plt.cm.cividis(np.linspace(0,1,len(range(36))))
        axs = fig.axes

        for chip in chips:
            if chip == 0:
                colors = colors_0
            elif chip == 1:
                colors = colors_1
            else:
                colors = colors_2
            for ch in chans:
                for half in range(2):
                    ax = axs[half]
                    sel = df.chip == chip
                    sel &= df.channel == ch
                    sel &= df.half == half
                    sel &= df.tot > 0
                    df_sel = df[sel]
                    #sel &= df.tot > 500
                    df_fit = df[sel]
                    prof = df_sel.groupby("q")["tot"].mean()
                    prof_fit = df_fit.groupby("q")["tot"].mean()
                    args = self.fit(prof_fit.index,prof_fit.values,p=[1.31,30])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['tot_slope'] = float(args[0])
                    nestedConf['roc'][int(chip)]['half'][int(half)]['ch'][int(ch)]['tot_intercept'] = float(args[1])
                    ax.plot(prof.index/1000, prof.values * 0.05,'-',color=colors[ch],label="ch%i" %ch)
                    ax.legend(ncol=2, loc = "lower right",fontsize=8)
                    ax.set_ylabel("tot")
                    ax.set_xlabel("charge [pC]")

                    ax = axs[half+2] 
                    ax.plot(prof.index/1000,(prof.values - self.reglinear(prof.index,*args))/40,"-", color=colors[ch])
                    ax.set_ylabel("INL [%]")
                    ax.set_xlabel("charge [pC]")
                    ax.set_ylim(-2,2)
        return nestedConf


    def makeResultPlot(self,indict,keys):
        fig = plt.figure(figsize=(15,8),constrained_layout=True)
        for key in keys:
            fig0 = plt.figure(figsize=(15,8),constrained_layout=True)
            channel = []
            res = []
            for half in range(2):
                for ch in range(36):
                    try:
                        val = indict['roc'][0]['half'][half]['ch'][ch].get(key)
                        if  val > 0:
                            res.append(val)
                            channel.append(ch+half*36)
                        else:
                            continue
                    except:
                        continue
            plt.plot(channel,res,'o',label=key)
            plt.legend(fontsize=12, loc="lower left",bbox_to_anchor=(1,0.5))
            plt.savefig(self.odir + key)

            plt.figure(fig.number)
            plt.plot(channel,res,'o',label=key)
            plt.legend(fontsize=12, loc="lower left",bbox_to_anchor=(1,0.5))
        plt.savefig(self.odir + "total")


if __name__ == "__main__":

	if len(sys.argv) == 2:
		indir = sys.argv[1]
		odir = sys.argv[1]

		ana = injection_scan_analyzer(odir=odir)
		files = glob.glob(indir+"/*.root")

		for f in files:
			ana.add(f)

		ana.mergeData()
		# injectedChannels = [10,30,66,46]
		injectedChannels = [i for i in range(72)]
		injectedChannels = [0, 0+18,0+36,0+36+18]

		ana.makePlots(injectedChannels)

	else:
		print("No argument given")
