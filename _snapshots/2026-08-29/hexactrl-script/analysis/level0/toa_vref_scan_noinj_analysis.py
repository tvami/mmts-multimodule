from level0.analyzer import *
import argparse
import yaml
import glob

    
class toa_vref_scan_noinj_analyzer(analyzer):

    def makePlots(self):
        cmap = mpl.colormaps['viridis']
        sel_data = self.data[['chip','half','channel','channeltype','adc_stdd','toa_efficiency','Toa_vref']].copy()
        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = sel_data[ ~sel_data['channel'].isin(unconnectedChannels) ]
        varlist = {
            'adc' : { 'name': 'adc_stdd', 'label' : 'Noise [ADC counts]' },
            'toa' : { 'name' : 'toa_efficiency', 'label' : 'ToA efficiency' }
        }

        for chip in sel_data.groupby('chip')['chip'].mean():
            chip_data = sel_data[ (sel_data['chip']==chip) & (sel_data['channeltype']==0) ]
            for var in varlist:
                fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
                axes[0].set_ylabel(varlist[var]['label'])
                for ax in axes:
                    ax.set_xlabel(r'TOA vref [DAC]')
                    ax.xaxis.grid(True)

                axes[0].set_title(f'chip{chip}, first half')
                axes[1].set_title(f'chip{chip}, second half')
                for channel in chip_data.groupby('channel')['channel'].mean():
                    data = chip_data.query( 'channel==%s'%(channel) ).sort_values('Toa_vref')
                    half = int(data['half'].iloc[0])
                    # print(half)
                    if half==0:
                        ax=axes[0]
                    else:
                        ax=axes[1]
                    ax.plot(data['Toa_vref'],data[varlist[var]['name']],marker='o',color=cmap((channel%36)/36.),label=r'Channel %d'%(channel))
                # for half in [0,1]:
                #     h,l=axes[half].get_legend_handles_labels()
                #     axes[half].legend(handles=h,labels=l,loc='upper right',ncol=2,fontsize=8)
                
                plt.savefig(f'{self.odir}/{var}_toa_vref_scan_chip{chip}.png', format='png', bbox_inches='tight') 
                plt.close()

        return
    
    def findVref(self):

        sel_data = self.data[['chip','channel','channeltype','toa_efficiency','Toa_vref']].copy()
        sel_data = sel_data[ sel_data['channeltype']==0 ] # for simplification
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
        for chip in sel_data['chip'].unique():
            chip=int(chip)
            if chip<len(rockeys):
                chip_key_name = rockeys[chip]
            yaml_dict[chip_key_name] = {
                'sc' : {
                    'ReferenceVoltage' : { 
                    }
                }
            }
            vrefs={
                0 : { 'Toa_vref' : 0},
                1 : { 'Toa_vref' : 0}
            }
            chip_data = sel_data[ sel_data['chip']==chip ]
            for ch in chip_data.groupby('channel')['channel'].mean():
                df_chn = chip_data.query('channel==%s' % (ch)).sort_values('Toa_vref')
                sel = df_chn['toa_efficiency']>0.01
                if sel.any() and (~sel).any():
                    vrefs[int(ch/36)]['Toa_vref'] = max(vrefs[int(ch/36)]['Toa_vref'],int(df_chn[sel]["Toa_vref"].max()))
            ## Adding some margin !
            vrefs[0]['Toa_vref'] = vrefs[0]['Toa_vref']+10
            vrefs[1]['Toa_vref'] = vrefs[1]['Toa_vref']+10
            yaml_dict[chip_key_name]['sc']['ReferenceVoltage']=vrefs
        with open(self.odir+'/toa_vref.yaml','w') as fout:
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
        
    ana = toa_vref_scan_noinj_analyzer(odir=odir)
    files = glob.glob(indir+"/*.root")
        
    for f in files:
        ana.add(f)
    ana.mergeData()

    ana.makePlots()
    ana.findVref()
    
