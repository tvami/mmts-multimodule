from level0.analyzer import *
from scipy.optimize import curve_fit
import glob

class inputdac_scan_analyzer(analyzer):

    def makePlots(self):
        cmap = cm.get_cmap('viridis')
        cmcmap = cm.get_cmap('Set1')
        nchip = len( self.data.groupby('chip').nunique() )        

        unconnectedChannels=[]#8,17,18,27,
                             #36+8,36+17,36+18,36+27]

        sel_data = self.data[['chip','half','channel','channeltype','adc_mean','adc_stdd','Inputdac']].copy()

        for chip in range(nchip):
            ####################################
			## let's plot pedestal vs phase: 
            ####################################

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            ax=axes[0]
            data = sel_data[ sel_data['chip']==chip ]
            chan_data = data[ (data['channeltype']<=1) & (data['half']==0) & (~data['channel'].isin(unconnectedChannels)) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Inputdac'], chan_data['adc_mean'], c=inv, cmap=cmap)
            
            # chan_data = data[ (data['channeltype']==100) & (data['half']==0) ].copy()
            # u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            # ax.scatter(chan_data['Inputdac'], chan_data['adc_mean'], c=inv, cmap=cmcmap)

            ax.set_title('First half')
            ax.set_xlabel(r'Inputdac')
            ax.set_ylabel(r'Pedestal [ADC counts]')

            ax=axes[1]
            chan_data = data[ (data['channeltype']<=1) & (data['half']==1) & (~data['channel'].isin(unconnectedChannels)) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Inputdac'], chan_data['adc_mean'], c=inv, cmap=cmap)
            
            # chan_data = data[ (data['channeltype']==100) & (data['half']==1) ].copy()
            # u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            # ax.scatter(chan_data['Inputdac'], chan_data['adc_mean'], c=inv, cmap=cmcmap)

            ax.set_title('Second half')
            ax.set_xlabel(r'Inputdac')

            plt.savefig("%s/pedestal_vs_inputdac_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            ax=axes[0]
            data = sel_data[ sel_data['chip']==chip ]
            chan_data = data[ (data['channeltype']<=1) & (data['half']==0) & (~data['channel'].isin(unconnectedChannels)) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Inputdac'], chan_data['adc_stdd'], c=inv, cmap=cmap)
            
            # chan_data = data[ (data['channeltype']==100) & (data['half']==0) ].copy()
            # u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            # ax.scatter(chan_data['Inputdac'], chan_data['adc_stdd'], c=inv, cmap=cmcmap)

            ax.set_title('First half')
            ax.set_xlabel(r'Inputdac')
            ax.set_ylabel(r'Noise [ADC counts]')

            ax=axes[1]
            chan_data = data[ (data['channeltype']<=1) & (data['half']==1) & (~data['channel'].isin(unconnectedChannels)) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Inputdac'], chan_data['adc_stdd'], c=inv, cmap=cmap)
            
            # chan_data = data[ (data['channeltype']==100) & (data['half']==1) ].copy()
            # u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            # ax.scatter(chan_data['Inputdac'], chan_data['adc_stdd'], c=inv, cmap=cmcmap)

            ax.set_title('Second half')
            ax.set_xlabel(r'Inputdac')

            plt.savefig("%s/noise_vs_inputdac_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 
            plt.close()


    def findInputdacs(self):
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','channel','channeltype','adc_mean','Inputdac']].copy()
        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc')==0:
                    rockeys.append(key)
        rockeys.sort()
        yaml_dict={}
        for chip in sel_data.groupby('chip')['chip'].mean():
            if chip<len(rockeys):
                chip_key_name = rockeys[chip]
            yaml_dict[chip_key_name] = {
                'sc' : {}
            }
            dacs={
                'ch' :    {ch : { 'Inputdac': 0 } for ch in range(72)},
                'calib' : {ch : { 'Inputdac': 0 } for ch in range(2) }
            }
            channeltypemap = {
                'ch' : 0,
                'calib': 1
            }

            for chtype in channeltypemap:
                chip_data = sel_data[ (sel_data['chip']==chip) & (sel_data['channeltype']==channeltypemap[chtype]) ]
                for ch in chip_data.groupby('channel')['channel'].mean():
                    df_chn = chip_data.query('channel==%s' % (ch)).sort_values('Inputdac')
                    sel = df_chn['adc_mean']<150
                    if sel.any() and (~sel).any():
                        dacs[ chtype ][ch]['Inputdac'] = int(df_chn[sel]['Inputdac'].min())
            yaml_dict[chip_key_name]['sc']=dacs

        with open(self.odir+'/inputdacs.yaml','w') as fout:
            yaml.dump(yaml_dict,fout)
        return
    

            
if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        ped_analyzer = inputdac_scan_analyzer(odir=odir)
        files = glob.glob(indir + "/pedestal_scan*.root")
        print(files)

        for f in files:
            ped_analyzer.add(f)

        ped_analyzer.mergeData()
        ped_analyzer.findInputdac()
    else:
        print("No argument given")
