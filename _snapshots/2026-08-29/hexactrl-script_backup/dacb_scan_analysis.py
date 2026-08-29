from level0.analyzer import *
from scipy.optimize import curve_fit
import glob
import uproot
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.offsetbox import AnchoredText
from matplotlib.ticker import MultipleLocator

class dacb_scan_analyzer(analyzer):

    def makePlots(self):
        # load data
        odir = self.odir 
        data = self.data[["chip", "half", "channel", "channeltype", "adc_median", "Dacb", "Sign_dac"]].copy()
        nchip = len(data["chip"].unique())
        Sign_dac = data['Sign_dac'].iloc[0]

        channels = self.target.copy()
        channeltype = channels["channeltype"].iloc[0]
        Gain_conv = channels["Gain_conv"].iloc[0]

        ch_list = channels["channel"].unique()
        nchannel = len(ch_list)
        vmin = min(ch_list)
        vmax = max(ch_list)

        # Select colormap to distinguish the channels
        cmap = cm.get_cmap('viridis', nchannel)
        cwidth = (vmax - vmin) / nchannel
        first_tick = vmin + (cwidth / 2.)
        ticks = np.arange(first_tick, first_tick + cwidth * nchannel, cwidth)     
        font_size = 6
        marker_size = 10

        for chip in range(nchip):
            fig, ax = plt.subplots(figsize = (16, 9))

            #for channel in channels["channel"].unique():
                # Select data 
            sel = data["chip"] == chip
                #sel &= data["channel"] == channel
            sel &= data["channeltype"] == channeltype
            if channeltype == 100:
                sel &= data["channel"] != 0
                sel &= data["channel"] != 2
                font_size = 12
                marker_size = 20

            plot_data = data[sel].copy()
                #ax.plot(plot_data["Dacb"], plot_data["adc_median"], '.', label = channel)

            #ax.legend(title = "Channel", fontsize = 10, loc = "best", ncol = 3)
            # Plot pedestal vs dacb
            fig, ax = plt.subplots(figsize = (16, 9))

            #u, inv = np.unique(plot_data["channel"].values, return_inverse = True)
            im = ax.scatter(plot_data["Dacb"], plot_data["adc_median"], c = plot_data["channel"], cmap = cmap, s = marker_size, alpha = 0.7, vmin = vmin, vmax = vmax)

            cbar = fig.colorbar(im, ax = ax, label = "Channel")
            cbar.set_ticks(ticks)
            cbar.set_ticklabels(ch_list)
            cbar.ax.tick_params(labelsize = font_size)
            ax.set_title("Pedestal vs DACb")
            ax.set_xlabel("DACb")
            ax.set_ylabel("Pedestal [ADC counts]")
            ax.grid()

            txt = "Channeltype: %d \nSign_dac: %d \nGain_conv: %d" %(channeltype, Sign_dac, Gain_conv)
            anchored_text = AnchoredText(txt, loc = 'lower right', prop={'fontsize': 20})
            ax.add_artist(anchored_text)

            plt.savefig("%s/pedestal_vs_dacb_chip%d_chtype%d.png" %(odir, chip, channeltype),format='png', bbox_inches='tight') 
            plt.close()

        # Plot trimmed_dacb distribution
        fig, ax = plt.subplots(figsize = (16, 9))

        for chip in range(nchip):
            values = channels["trimmed_dacb"].values
            #print(values)
            binning = np.arange(min(values) - 0.5, max(values) + 0.5 + 1, 1)
            width = 1
            ax.hist(values, bins = binning, width = width, label = "chip %d" %chip, alpha = 0.7)

        ax.xaxis.set_major_locator(MultipleLocator(1)) 
        ax.set_xlabel("Best DACb values found")
        ax.set_ylabel("# of channels")
        ax.set_title("Best DACb value distribution")
        ax.legend()

        txt = "Channeltype: %d \nSign_dac: %d \nGain_conv: %d" %(channeltype, Sign_dac, Gain_conv)
        anchored_text = AnchoredText(txt, loc = 'lower right', prop={'fontsize': 20})
        ax.add_artist(anchored_text)

        plt.savefig("%s/trimmed_dacb_distr_chip%d_chtype%d.png" %(odir, chip, channeltype),format='png', bbox_inches='tight') 
        plt.close()


        '''
        # Here in case we want to perform a linear fit on normal channels
        fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=False)
        fitParams = pd.read_hdf(self.odir+'/dacb_scan.h5','dacb_scan')
        alpha_hists = []
        beta_hists = []
        labels=[]
        for chip in range(nchip):
            sel = fitParams.chip == chip
            #sel &= fitParams.half==half
            alpha_hists.append( fitParams[sel]['alpha'] )
            beta_hists.append( fitParams[sel]['beta'] )
            labels.append( 'chip %d' %(chip) )
            
        ax1=axes[0]
        ax1.hist(alpha_hists,label=labels)
        ax1.set_title('Slope of dacb scan')
        plt.xlabel(r'Slope')
        plt.ylabel(r'# channels')
        h,l=ax1.get_legend_handles_labels() # get labels and handles from ax1
        ax1.legend(handles=h,labels=l,loc='upper left',fontsize=12,ncol=2)


        ax2=axes[1]
        ax2.hist(beta_hists,label=labels)
        ax2.set_title('Offset of dacb scan')
        plt.xlabel(r'Offset')
        plt.ylabel(r'# channels')
        h,l=ax2.get_legend_handles_labels() # get labels and handles from ax1
        ax2.legend(handles=h,labels=l,loc='upper left',fontsize=12,ncol=2)
        plt.savefig("%s/dacb_scan_fitparams.png"%(self.odir))
        plt.close()
        '''

    def retrieve_ped(self, indir):
        # indir is dir where pedestal run files are
        print("Retrieving target pedestals")
        f = uproot.open(indir + "/pedestal_run0.root")
        df = f["runsummary/summary"].pandas.df()
        self.target = df[["chip", "channel", "channeltype", "adc_median"]].copy() # target ped = adc_median
        self.target = self.target.rename(columns = {"adc_median": "target_ped"})
        print(self.target)

    # trimmed dacb for either cm or normal channels 
    def trimmed_dacb(self, data, target):
        df = data[["adc_median", "Dacb"]].astype(int).reset_index() # without astype it messes negative ints
        df["ped_diff"] = abs(df["adc_median"] - target)
        best_dacb = df.loc[df["ped_diff"].idxmin(), "Dacb"]
        
        return best_dacb

    # keep fit for normal channels 
    # might be faster if we can take less points 
    def fit(self, df, xcol_name, ycol_name, Sign_dac = 0):
        sign = -1
        if Sign_dac == 1:
            sign = 1

        sel = df.adc_median > 0
        x0 = sign * df.loc[sel, xcol_name]
        y0 = df.loc[sel, ycol_name]
        if len(x0) > 1:
            popt, pcov = curve_fit(lambda x, a, b: a * x + b, x0, y0, p0=[6., x0.min()])
        else:
            popt = [0, 0] # means all dacb give 0 pedestal (horizontal line)
        return popt[0],popt[1]

    def determine_DACb(self, channeltype = 100, Gain_conv = 10): # channeltype 0 = normal ch, channeltype 100 = cm ch            
        print('Determining DACb values')

        odir = self.odir

        # load target pedestal values
        channels = self.target.astype(int).copy()
        sel = channels['channeltype'] == channeltype
        if channeltype == 100:
            sel &= channels['channel'] != 0
            sel &= channels['channel'] != 2
        channels = channels[sel]

        # initialize trimmed_dacb
        zeros = np.zeros(len(channels.index), dtype = int)
        channels["trimmed_dacb"] = zeros
        channels["Gain_conv"] = Gain_conv
                
        '''
        # Here in case we want to perform a linear fit on the normal channels
        zeros = np.zeros( len(channels) )
        channels['alpha'] = zeros
        channels['beta'] = zeros
        if channeltype == 100:
            channels['gamma'] = zeros
            data = self.data[['chip','channel','channeltype','adc_median','CM_Dacb', 'Sign_dac']].copy()
        elif channeltype == 0:
            data = self.data[['chip','channel','channeltype','adc_median','Ch_Dacb', 'Sign_dac']].copy()
        '''

        # Load data
        data = self.data[["chip", "half", "channel", "channeltype", "adc_median", "Dacb", "Sign_dac"]].copy()
        data = data[ data['channeltype'] == channeltype ]

        # Apply trimmed_dacb to find best dacb on each of the channels under study
        for chip in channels["chip"].unique():
            for channel in channels["channel"].unique():
                sel_ch = channels["chip"] == chip
                sel_ch &= channels["channel"] == channel
                target = channels.loc[sel_ch, "target_ped"].iloc[0]
                
                sel_data = data["chip"] == chip
                sel_data &= data["channel"] == channel

                channels.loc[sel_ch, "trimmed_dacb"] = self.trimmed_dacb(data[sel_data], target)

        # Add Sign_dac to working dataframe 
        channels["Sign_dac"] = data["Sign_dac"].iloc[0]

        # Print trimmed_dacb found
        print("Best dacb values determined.")
        print(channels)

        '''
        # Here in case we want to perform a linear fit on the normal channels
        for index, row in channels.iterrows():
            sel = data.chip==row['chip']
            sel &= data.channel==row['channel']
            #sel &= data.half==row['half']
            sel &= data.channeltype==row['channeltype']
            sel &= data.adc_median>10 ## avoid wrong data setting
            fitparams = self.fit(data[sel])
            if len(fitparams) > 2:
                alpha, beta, gamma = fitparams
                channels.loc[index, 'gamma'] = gamma
            else:
                alpha,beta = fitparams
            channels.loc[index, 'alpha'] = alpha
            channels.loc[index, 'beta' ] = beta
        
        channels['Sign_dac'] = data['Sign_dac'].to_numpy()[0]
        #dacb_scan_summary = channels[['chip','channel','channeltype','alpha','beta','adc_median']].to_hdf(self.odir+'/dacb_scan.h5', key='dacb_scan', mode='w')
        '''

        # Save the values found in self, h5 and yaml for config
        self.target = channels

        nchip = len(data["chip"].unique())        
        yaml_file = odir + '/trimmed_dacb.yaml'
        if os.path.exists(yaml_file):
            with open(yaml_file) as fin:
                yaml_dict = yaml.safe_load(fin)
        else:
            yaml_dict = {}

        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc') ==0 :
                    rockeys.append(key)
        rockeys.sort()
        
        for chip in range(nchip):
            channel_dict = {}
            calib_dict = {}
            cm_dict = {}
            '''
            # Here in case we want to perform a linear fit on normal channels
            if channeltype == 0:
                channels['trimmed_dacb'] = channels.apply( lambda x: int(round( (x.adc_median-x.beta)/x.alpha )) if x.adc_median-x.beta>0 else 0, axis=1 ) # maybe 'if' will change with Sign_Dacb
            elif channeltype == 100:
                #channels['trimmed_dacb'] = channels.apply( lambda x: 
            print(channels)
            '''
            for index, row in channels.iterrows():
                adict = { 
                   "Dacb" : int(row["trimmed_dacb"].item())
                }
                if row["channeltype"] == 0:
                    channel_dict[int(row["channel"].item())] = adict
                elif row["channeltype"] == 1:
                    calib_dict[int(row["channel"].item())] = adict
                elif row["channeltype"] == 100:
                    cm_dict[int(row["channel"].item())] = adict

            if chip < len(rockeys):
                chip_key_name = rockeys[chip]
                if chip_key_name in yaml_dict:
                    yaml_dict[chip_key_name]['sc']['ch'] = channel_dict
                else: 
                    yaml_dict[chip_key_name] = {
                        'sc' : {
                            'ch' : channel_dict,
                            'cm' : cm_dict,
                            'calib' : calib_dict
                        } 
                    }
            else :
                print("WARNING : Dacb will not be saved for ROC %d"%(chip))
        
        with open(yaml_file, 'w') as fout:
            yaml.dump(yaml_dict, fout)

        if channeltype == 0:
            key = "ch"
        elif channeltype == 100:
            key = "cm"
        channels.to_hdf(odir + "dacb_scan.h5", key = key)

if __name__ == "__main__":

	if len(sys.argv) == 3:
		indir = sys.argv[1]
		odir = sys.argv[2]

		dacb_analyzer = dacb_scan_analyzer(odir=odir)
		files = glob.glob(indir+"/dacb_scan*.root")
		print(files)

		for f in files:
			dacb_analyzer.add(f)

		dacb_analyzer.mergeData()
		dacb_analyzer.determine_DACb()
		dacb_analyzer.makePlots()

	else:
		print("No argument given")
