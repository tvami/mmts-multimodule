from level0.analyzer import *
import argparse
import yaml
import glob

class toa_vref_scan_analyzer(analyzer):

    def makePlots(self):
        nchip = len( self.data.groupby('chip').nunique() )        
        cmap = cm.get_cmap('viridis')

        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = self.data[['chip','channel','channeltype','Calib','toa_efficiency','injectedChannels','Toa_vref']].copy()
        sel_data = sel_data[ (sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
        sel_data = sel_data[ ~sel_data['channel'].isin(unconnectedChannels) ]
        
        print(sel_data.describe())
        for chip in sel_data.groupby('chip')['chip'].mean():
            chip_data = sel_data[ sel_data['chip']==chip ]

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            axes[0].set_ylabel('toa_efficiency')

            for ax in axes:
                ax.set_xlabel(r'TOA vref [DAC]')
                ax.xaxis.grid(True)

            axes[0].set_title(f'chip{chip}, first half')
            axes[1].set_title(f'chip{chip}, second half')
            chanColor=0
            for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean():
                df_chn = chip_data.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('Toa_vref')
                if ch<36:
                    ax=axes[0]
                else:
                    ax=axes[1]
                ax.plot(df_chn.Toa_vref,df_chn.toa_efficiency,marker='o',color=cmap((ch%36)/36.),label=r'Channel %d'%(ch))

            for half in [0,1]:
                h,l=axes[half].get_legend_handles_labels()
                axes[half].legend(handles=h,labels=l,loc='upper right',ncol=2,fontsize=8)
                
            plt.savefig(f'{self.odir}/toa_vref_scan_chip{chip}.png', format='png', bbox_inches='tight') 
            plt.close()

        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = self.data[['chip','channel','channeltype','Calib','toa_efficiency','injectedChannels','Toa_vref']].copy()
        sel_data = sel_data[ (~sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
        sel_data = sel_data[ ~sel_data['channel'].isin(unconnectedChannels) ]
        
        for chip in sel_data.groupby('chip')['chip'].mean():
            chip_data = sel_data[ sel_data['chip']==chip ]

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            axes[0].set_ylabel('toa_efficiency')

            for ax in axes:
                ax.set_xlabel(r'TOA vref [DAC]')
                ax.xaxis.grid(True)

            axes[0].set_title(f'chip{chip}, first half')
            axes[1].set_title(f'chip{chip}, second half')
            chanColor=0
            for ch in chip_data.groupby('channel')['channel'].mean():
                df_chn = chip_data.query('channel==%s' % (ch)).sort_values('Toa_vref')
                if ch<36:
                    ax=axes[0]
                else:
                    ax=axes[1]
                ax.plot(df_chn.Toa_vref,df_chn.toa_efficiency,marker='o',color=cmap((ch%36)/36.),label=r'Channel %d'%(ch))

            for half in [0,1]:
                h,l=axes[half].get_legend_handles_labels()
                axes[half].legend(handles=h,labels=l,loc='upper right',ncol=2,fontsize=8)
                
            plt.savefig(f'{self.odir}/toa_vref_scan_chip{chip}_noinj.png', format='png', bbox_inches='tight') 
            plt.close()


        return
    
    def findVref(self):
        nchip = len( self.data.groupby('chip').nunique() )        
        
        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = self.data[['chip','channel','channeltype','Calib','toa_efficiency','injectedChannels','Toa_vref']].copy()
        sel_data = sel_data[ (sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
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
                0 : { 'Toa_vref' : 1023},
                1 : { 'Toa_vref' : 1023}
            }
            # if trim init at 31
            means = {0:[], 1:[]}
            chip_data = sel_data[ sel_data['chip']==chip ]
            for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean():
                df_chn = chip_data.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('Toa_vref')
                sel0 = df_chn['toa_efficiency']>0.5
                sel1 = ~sel0
                if sel0.any() and sel1.any():
                    means[int(ch/36)].append( int(df_chn[sel0]["Toa_vref"].max()) )

            means[0] = np.array(means[0]) 
            means[1] = np.array(means[1])
            print(chip,means)
            vrefs[0]['Toa_vref'] = np.quantile(means[0],0.5,interpolation='lower') if len(means[0])>0 else 1023
            vrefs[1]['Toa_vref'] = np.quantile(means[1],0.5,interpolation='lower') if len(means[1])>0 else 1023 
            print( vrefs[0]['Toa_vref'] ) 
            print( vrefs[1]['Toa_vref'] )
            vrefs[0]['Toa_vref'] = int( vrefs[0]['Toa_vref'] )
            vrefs[1]['Toa_vref'] = int( vrefs[1]['Toa_vref'] )

            # # if trim init at 0
            # vals = {0:[], 1:[]}
            # chip_data = sel_data[ sel_data['chip']==chip ]
            # for ch in chip_data.groupby('injectedChannels')['injectedChannels'].mean():
            #     df_chn = chip_data.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('Toa_vref')
            #     sel0 = df_chn['toa_efficiency']>0.5
            #     sel1 = ~sel0
            #     if sel0.any() and sel1.any():
            #         vals[int(ch/36)].append( int(df_chn[sel0]["Toa_vref"].max()) )

            # vals[0] = np.array(vals[0]) 
            # vals[1] = np.array(vals[1])
            # print(chip,vals)
            # if len(vals[0].tolist())>0:
            #     vals[0] = vals[0][abs(vals[0] - np.mean(vals[0])) <= 3 * np.std(vals[0])]
            #     vrefs[0]['Toa_vref'] = np.max( vals[0] ) 
            # if len(vals[1].tolist())>0:
            #     vals[1] = vals[1][abs(vals[1] - np.mean(vals[1])) <= 3 * np.std(vals[1])] 
            #     vrefs[1]['Toa_vref'] = np.max( vals[1] )
            # print( vrefs[0]['Toa_vref'] ) 
            # print( vrefs[1]['Toa_vref'] ) 
            # vrefs[0]['Toa_vref'] = int( vrefs[0]['Toa_vref'] )
            # vrefs[1]['Toa_vref'] = int( vrefs[1]['Toa_vref'] )

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
        
    ana = toa_vref_scan_analyzer(odir=odir)
    files = glob.glob(indir+"/*.root")
        
    for f in files:
        ana.add(f)
    ana.mergeData()

    ana.makePlots()
    ana.findVref()
    
