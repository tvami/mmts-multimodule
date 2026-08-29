from level0.analyzer import *
from scipy.optimize import curve_fit
import glob

class pedestal_scan_analyzer(analyzer):

    def makePlots(self):
        cmap = mpl.colormaps.get_cmap('viridis')
        cmcmap = mpl.colormaps.get_cmap('Set1')
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','half','channel','channeltype','adc_mean','trim_inv']].copy()
        
        for chip in range(nchip):
            ####################################
			## let's plot pedestal vs phase: 
            ####################################

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            ax=axes[0]
            data = sel_data[ sel_data['chip']==chip ]
            chan_data = data[ (data['channeltype']<=1) & (data['half']==0) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['trim_inv'], chan_data['adc_mean'], c=inv, cmap=cmap)
            
            chan_data = data[ (data['channeltype']==100) & (data['half']==0) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['trim_inv'], chan_data['adc_mean'], c=inv, cmap=cmcmap)

            ax.set_title('First half')
            ax.set_xlabel(r'trim_inv')
            ax.set_ylabel(r'Pedestal [ADC counts]')

            ax=axes[1]
            chan_data = data[ (data['channeltype']<=1) & (data['half']==1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['trim_inv'], chan_data['adc_mean'], c=inv, cmap=cmap)
            
            chan_data = data[ (data['channeltype']==100) & (data['half']==1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['trim_inv'], chan_data['adc_mean'], c=inv, cmap=cmcmap)

            ax.set_title('Second half')
            ax.set_xlabel(r'trim_inv')

            plt.savefig("%s/pedestal_vs_refdacinv_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 
            plt.close()

        fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=False)
        fitParams = pd.read_hdf(self.odir+'/pedestal_scan.h5','pedestal_scan')
        alpha_hists = []
        beta_hists = []
        labels=[]
        for chip in range(nchip):
            for half in range(2):
                sel = fitParams.chip==chip
                sel &= fitParams.half==half
                alpha_hists.append( fitParams[sel]['alpha'] )
                beta_hists.append( fitParams[sel]['beta'] )
                labels.append( 'chip %d ; half %d'%(chip,half) )
            
        ax1=axes[0]
        ax1.hist(alpha_hists,label=labels)
        ax1.set_title('Slope of pedestal scan')
        plt.xlabel(r'Slope')
        plt.ylabel(r'# channels')
        h,l=ax1.get_legend_handles_labels() # get labels and handles from ax1
        ax1.legend(handles=h,labels=l,loc='upper left',fontsize=12,ncol=2)


        ax2=axes[1]
        ax2.hist(beta_hists,label=labels)
        ax2.set_title('Offset of pedestal scan')
        plt.xlabel(r'Offset')
        plt.ylabel(r'# channels')
        h,l=ax2.get_legend_handles_labels() # get labels and handles from ax1
        ax2.legend(handles=h,labels=l,loc='upper left',fontsize=12,ncol=2)
        plt.savefig("%s/pedestal_scan_fitparams.png"%(self.odir))
        plt.close()


    def fit(self,sel):
        x0 = self.data[sel]['trim_inv']
        y0 = self.data[sel]['adc_mean']
        if len(x0)>2:
            popt, pcov = curve_fit(lambda x,a,b:a*x+b, x0, y0, p0=[6,x0.min()])
        else:
            popt = [1,0]
        return popt[0],popt[1]

    def determine_pedDAC(self):            
        channels = self.data.groupby(['channel','channeltype','chip']).mean().reset_index() #one entry per channel
        zeros = np.zeros( len(channels) )
        channels['alpha'] = pd.Series(zeros,index=channels.index)
        channels['beta'] = pd.Series(zeros,index=channels.index)
        
        data = self.data[['half','chip','channel','channeltype','adc_mean','trim_inv']].copy()
        for index, row in channels.iterrows():
            sel = data.chip==row['chip']
            sel &= data.channel==row['channel']
            sel &= data.half==row['half']
            sel &= data.channeltype==row['channeltype']
            sel &= data.adc_mean>10 ## avoid wrong data setting
            sel &= data.adc_mean < 1000  ## avoid wrong data setting
            alpha,beta = self.fit(sel)
            channels.loc[index, 'alpha'] = alpha
            channels.loc[index, 'beta' ] = beta
        pedestal_scan_summary = channels[['chip','half','channel','channeltype','alpha','beta']].to_hdf(self.odir+'/pedestal_scan.h5', key='pedestal_scan', mode='w')
        
        nchip = len( self.data.groupby('chip').nunique() )        
        yaml_dict = {}
        
        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc')==0:
                    rockeys.append(key)
        rockeys.sort()
        
        for chip in range(nchip):
            channel_dict = {}
            calib_dict = {}
            cm_dict = {}
            for half in range(len( self.data.groupby('half').nunique() )):
                data = channels[ (channels['chip']==chip) & (channels['half']==half) ].copy()
                sel = data.channeltype!=100
                iqr = data[sel]['beta'].quantile(0.75) - data[sel]['beta'].quantile(0.25)
                sel &= data.beta - data.beta.mean() < 2*iqr
                target = data[ sel ]['beta'].max()
                
                print( chip, target, data.beta.mean(), iqr )
                if not target:
                    continue
                data['trimmed_ref_dac'] = data.apply( lambda x: int(round( (target-x.beta)/x.alpha )) if target-x.beta>0 and x.alpha>0 else 0, axis=1 )
                for index, row in data.iterrows():
                    adict = { 
                        'trim_inv' : int(row['trimmed_ref_dac'].item()) if row['trimmed_ref_dac'].item()<63 else 63
                    }
                    if row.channeltype==0:
                        channel_dict[int(row.channel.item())] = adict
                    elif row.channeltype==1:
                        calib_dict[int(row.channel.item())] = adict
                    elif row.channeltype==100:
                        cm_dict[int(row.channel.item())] = adict

            if chip<len(rockeys):
                chip_key_name = rockeys[chip]
                yaml_dict[chip_key_name] = {
                    'sc' : {
                        'ch' : channel_dict,
                        'cm' : cm_dict,
                        'calib' : calib_dict
                    } 
                }
            else :
                print("WARNING : trimmed trim_inv will not be saved for ROC %d"%(chip))

        with open(self.odir+'/trimmed_pedestal.yaml','w') as fout:
            yaml.dump(yaml_dict,fout)


    def addSummary(self):            
        channels = self.data.groupby(['channel','channeltype','chip']).mean().reset_index() #one entry per channel
        # channels = self.dataFrames[0] #one entry per channel
        zeros = np.zeros( len(channels) )
        channels['alpha'] = pd.Series(zeros,index=channels.index)
        channels['beta'] = pd.Series(zeros,index=channels.index)
        
        data = self.data[['half','chip','channel','channeltype','adc_mean','trim_inv']].copy()
        for index, row in channels.iterrows():
            sel = data.chip==row['chip']
            sel &= data.channel==row['channel']
            sel &= data.half==row['half']
            sel &= data.channeltype==row['channeltype']
            sel &= data.adc_mean>10 ## avoid wrong data setting
            alpha,beta = self.fit(sel)
            channels.loc[index, 'alpha'] = alpha
            channels.loc[index, 'beta' ] = beta
                
        # add summary information
        self._summary['bad_channels_ref_dac'] = {
            'rejection criteria': '(offset > target) or (target-offset)/slope > 63'
        }
        self._summary['bad_channels_pedestal'] = {
            'rejection criteria': 'slope < 1 or offset > 500 or offset==0 (invalid fit)'
        }
        nchip = len( self.data.groupby('chip').nunique() )        
        for chip in range(nchip):
            channel_dict = {}
            calib_dict = {}
            cm_dict = {}
            bad_ref_dac_chns = { 'ch':[],
                             'calib':[],
                             'cm':[] }
            bad_channels = { 'ch':[],
                             'calib':[],
                             'cm':[] }
            for half in range(len( self.data.groupby('half').nunique() )):
                data = channels[ (channels['chip']==chip) & (channels['half']==half) ].copy()
                sel = data.channeltype!=100
                iqr = data[sel]['beta'].quantile(0.75) - data[sel]['beta'].quantile(0.25)
                sel &= data.beta - data.beta.mean() < 2*iqr
                target = data[ (data['channeltype']!=100) & ( (data['beta']-data['beta'].mean())<3*data['beta'].quantile() )]['beta'].max()
                data['trimmed_ref_dac'] = data.apply( lambda x: int(round( (target-x.beta)/x.alpha )) if target-x.beta>0 else 0, axis=1 )
                badrefdacchns = data.query(f'trimmed_ref_dac>63 | {target}<beta')
                bad_ref_dac_chns['ch'].extend(badrefdacchns[ badrefdacchns['channeltype']==0 ]['channel'].to_list())
                bad_ref_dac_chns['calib'].extend(badrefdacchns[ badrefdacchns['channeltype']==1 ]['channel'].to_list())
                bad_ref_dac_chns['cm'].extend(badrefdacchns[ badrefdacchns['channeltype']==100 ]['channel'].to_list())
                badchannels = data.query('(alpha<1 | beta>500 | beta==0)')
                bad_channels['ch'].extend(badchannels[ badchannels['channeltype']==0 ]['channel'].to_list())
                bad_channels['calib'].extend(badchannels[ badchannels['channeltype']==1 ]['channel'].to_list())
                bad_channels['cm'].extend(badchannels[ badchannels['channeltype']==100 ]['channel'].to_list())

            self._summary['bad_channels_ref_dac']['chip%d' % chip] = bad_ref_dac_chns
            self._summary['bad_channels_ref_dac']['chip%d' % chip]['total'] = len(bad_ref_dac_chns['ch']) + len(bad_ref_dac_chns['cm']) + len(bad_ref_dac_chns['calib'])
            
            self._summary['bad_channels_pedestal']['chip%d' % chip] = bad_channels
            self._summary['bad_channels_pedestal']['chip%d' % chip]['total'] = len(bad_channels['ch']) + len(bad_channels['cm']) + len(bad_channels['calib'])

            

if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        ped_analyzer = pedestal_scan_analyzer(odir=odir)
        files = glob.glob(indir + "/pedestal_scan*.root")
        print(files)

        for f in files:
            ped_analyzer.add(f)


        ped_analyzer.mergeData()
        ped_analyzer.determine_pedDAC()
        ped_analyzer.makePlots()
        # ped_analyzer.addSummary()
        # ped_analyzer.writeSummary()
    else:
        print("No argument given")
