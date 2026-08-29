from level0.analyzer import *
import argparse
import yaml
import glob

class tot_trim_scan_analyzer(analyzer):

    def makePlots(self):
        nchip = len( self.data.groupby('chip').nunique() )        
        cmap = cm.get_cmap('viridis')

        sel_data = self.data[['chip','channel','channeltype','Calib','tot_efficiency','injectedChannels','trim_tot']].copy()
        sel_data = sel_data[ (sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
        
        print(sel_data.describe())
        for chip in sel_data.groupby('chip')['chip'].mean():
            chip_data = sel_data[ sel_data['chip']==chip ]

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            axes[0].set_ylabel('tot_efficiency')

            for ax in axes:
                ax.set_xlabel(r'trim TOT [DAC]')
                ax.xaxis.grid(True)

            axes[0].set_title(f'chip{chip}, first half')
            axes[1].set_title(f'chip{chip}, second half')
            chanColor=0
            for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean():
                df_chn = chip_data.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('trim_tot')
                if ch<36:
                    ax=axes[0]
                else:
                    ax=axes[1]
                ax.plot(df_chn.trim_tot,df_chn.tot_efficiency,marker='o',color=cmap((ch%36)/36.),label=r'Channel %d'%(ch))

            for half in [0,1]:
                h,l=axes[half].get_legend_handles_labels()
                axes[half].legend(handles=h,labels=l,loc='upper right',ncol=2,fontsize=8)
                
            plt.savefig(f'{self.odir}/trim_tot_scan_chip{chip}.png', format='png', bbox_inches='tight') 
            plt.close()

        return
    
    def findTrim(self):
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','channel','channeltype','Calib','tot_efficiency','injectedChannels','trim_tot']].copy()
        sel_data = sel_data[ (sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc')==0:
                    rockeys.append(key)
        rockeys.sort()
        yaml_dict={}
        for chip in sel_data.groupby('chip')['chip'].mean():
            # if chip+1<len(rockeys):
            #     chip_key_name = rockeys[chip+1]
            if chip<len(rockeys):
                chip_key_name = rockeys[chip]
            yaml_dict[chip_key_name] = {
                'sc' : {
                    'ch' : { },
                    # 'calib' : { }
                }
            }
            chip_data = sel_data[ sel_data['chip']==chip ]
            trims = {
                ch: {
                    'max0' : chip_data['trim_tot'].min(),
                    'min1' : chip_data['trim_tot'].max() }
                for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean()
            }
            for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean():
                df_chn = chip_data.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('trim_tot')
                sel1 = df_chn['tot_efficiency']>0.5
                sel0 = ~sel1
                if sel1.any() and sel0.any():
                    trims[ch]['max0'] = int(df_chn[sel0]["trim_tot"].max())
                    trims[ch]['min1'] = int(df_chn[sel1]["trim_tot"].min())
                    yaml_dict[chip_key_name]['sc']['ch'][ch] = { 'trim_tot' : int( trims[ch]['max0'] + (trims[ch]['min1'] - trims[ch]['max0'])/2 ) }
        with open(self.odir+'/trimmed_tot.yaml','w') as fout:
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
        
    ana = tot_trim_scan_analyzer(odir=odir)
    files = glob.glob(indir+"/*.root")
        
    for f in files:
        ana.add(f)
    ana.mergeData()

    ana.makePlots()
    ana.findTrim()
    
