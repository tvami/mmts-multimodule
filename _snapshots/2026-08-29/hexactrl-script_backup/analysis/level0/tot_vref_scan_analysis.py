from level0.analyzer import *
import argparse
import yaml
import glob

class tot_vref_scan_analyzer(analyzer):

    def makePlots(self):
        nchip = len( self.data.groupby('chip').nunique() )        
        cmap = cm.get_cmap('viridis')

        sel_data = self.data[['chip','channel','channeltype','Calib','tot_efficiency','injectedChannels','Tot_vref']].copy()
        sel_data = sel_data[ (sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = sel_data[ ~sel_data['channel'].isin(unconnectedChannels) ]
       
        print(sel_data.describe())
        for chip in sel_data.groupby('chip')['chip'].mean():
            chip_data = sel_data[ sel_data['chip']==chip ]

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            axes[0].set_ylabel('tot_efficiency')

            for ax in axes:
                ax.set_xlabel(r'TOT vref [DAC]')
                ax.xaxis.grid(True)

            axes[0].set_title(f'chip{chip}, first half')
            axes[1].set_title(f'chip{chip}, second half')
            chanColor=0
            for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean():
                df_chn = chip_data.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('Tot_vref')
                if ch<36:
                    ax=axes[0]
                else:
                    ax=axes[1]
                ax.plot(df_chn.Tot_vref,df_chn.tot_efficiency,marker='o',color=cmap((ch%36)/36.),label=r'Channel %d'%(ch))

            for half in [0,1]:
                h,l=axes[half].get_legend_handles_labels()
                axes[half].legend(handles=h,labels=l,loc='upper right',ncol=2,fontsize=8)
                
            plt.savefig(f'{self.odir}/tot_vref_scan_chip{chip}.png', format='png', bbox_inches='tight') 
            plt.close()

        return
    
    def findVref(self):
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','channel','channeltype','Calib','tot_efficiency','injectedChannels','Tot_vref']].copy()
        sel_data = sel_data[ (sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = sel_data[ ~sel_data['channel'].isin(unconnectedChannels) ]
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
                'sc' : {
                    'ReferenceVoltage' : { 
                    }
                }
            }
            vrefs={
                0 : { 'Tot_vref' : 0},
                1 : { 'Tot_vref' : 0}
            }
            means = {0:[], 1:[]}
            chip_data = sel_data[ sel_data['chip']==chip ]
            for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean():
                df_chn = chip_data.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('Tot_vref')
                sel0 = df_chn['tot_efficiency']>0.5
                sel1 = ~sel0
                if sel0.any() and sel1.any():
                    means[int(ch/36)].append( int(df_chn[sel0]["Tot_vref"].max()) )

            means[0] = np.array(means[0]) 
            means[1] = np.array(means[1])
            print(chip,means)
            vrefs[0]['Tot_vref'] = np.quantile(means[0],0.5,interpolation='lower') if len(means[0])>0 else 1023
            vrefs[1]['Tot_vref'] = np.quantile(means[1],0.5,interpolation='lower') if len(means[1])>0 else 1023 
            vrefs[0]['Tot_vref'] = int( vrefs[0]['Tot_vref'] )
            vrefs[1]['Tot_vref'] = int( vrefs[1]['Tot_vref'] )

            yaml_dict[chip_key_name]['sc']['ReferenceVoltage']=vrefs
        with open(self.odir+'/tot_vref.yaml','w') as fout:
            yaml.dump(yaml_dict,fout)
        return
    
    
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', dest='indir', action='store',
                        help='input directory with root files')
    parser.add_argument('-o', dest='odir', action='store',
                        help='output directory with root files')
        
    args = parser.parse_args()
    indir = args.indir
    odir = args.odir
    if not odir:
        odir=indir
        
    ana = tot_vref_scan_analyzer(odir=odir)
    files = glob.glob(indir+"/*.root")
        
    for f in files:
        ana.add(f)
    ana.mergeData()

    ana.makePlots()
    ana.findVref()
    
