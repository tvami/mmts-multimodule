from level0.analyzer import *
import glob

class phase_scan_analyzer(analyzer):

    def makePlots(self):
        cmap = cm.get_cmap('cool')
        cmcmap = cm.get_cmap('Set1')
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','channel','half','channeltype','adc_mean','adc_stdd','Phase','adc_median']].copy()
        sel = sel_data.adc_mean < 1000 
        sel_data = sel_data[sel]
        # sel_data['half'] = sel_data.apply( lambda x: x.chip*10 if (x.channeltype==0 and x.channel<36) or (x.channeltype==1 and x.channel==0) or (x.channeltype==100 and x.channel<2) # first half
        #                                    else x.chip*10 + 1,
        #                                    axis=1
        #                                )

        for chip in range(nchip):

            ####################################
            ## let's plot pedestal vs phase: 
            ####################################
            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=False)

            ax=axes[0]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==0) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_mean'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_mean'], c=inv, cmap=cmap)

            ax.set_title('First half')
            ax.set_xlabel(r'Phase ')
            ax.set_ylabel(r'Pedestal [ADC counts]')
                
            ax=axes[1]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==1) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_mean'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_mean'], c=inv, cmap=cmap)

            ax.set_title('Second half')
            ax.set_xlabel(r'Phase ')

            plt.savefig("%s/pedestal_vs_phase_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 
            plt.close()

            # ####################################
            # ## let's also plot noise vs phase: 
            # ####################################

            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=False)
            ax=axes[0]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==0) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_stdd'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_stdd'], c=inv, cmap=cmap)

            ax.set_title('First half')
            ax.set_xlabel(r'Phase ')
            ax.set_ylabel(r'Noise [ADC counts]')

            ax=axes[1]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==1) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_stdd'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Phase'], chan_data['adc_stdd'], c=inv, cmap=cmap)

            ax.set_title('Second half')
            ax.set_xlabel(r'Phase ')

            plt.savefig("%s/noise_vs_phase_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight')
            plt.close()
            # plt.savefig("%s/noise_vs_phase_chip%d.pdf"%(self.odir,chip),format='pdf',bbox_inches='tight') 

            medians = sel_data[ (sel_data['chip']==chip) & (sel_data['channeltype']==0) ].groupby(['half','Phase']).median().reset_index()
            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=False)
            for half in range(2):
                ax=axes[half]
                half_data = medians[ medians['half']==half ]
                ax.scatter(half_data['Phase'], half_data['adc_mean'], color='blue')

                ax.set_title('Half %d'%(half))
                ax.set_xlabel(r'Phase ')
                if half==0 :
                    ax.set_ylabel(r'Median of channel pedestals [ADC counts]',fontsize=20)
            plt.savefig("%s/pedestal_vs_phase_chip%d_all.png"%(self.odir,chip),format='png',bbox_inches='tight')
            # plt.savefig("%s/pedestal_vs_phase_chip%d_all.pdf"%(self.odir,chip),format='pdf',bbox_inches='tight') 

            data = sel_data[ (sel_data['chip']==chip) & (sel_data['adc_stdd']>0) ]
            maxped = data[ data['channeltype']!=100 ].groupby(['channel','channeltype']).max().reset_index()
            minped = data[ data['channeltype']!=100 ].groupby(['channel','channeltype']).min().reset_index()
            fig, ax = plt.subplots(figsize=(16,9))
            ax.hist( (maxped-minped)['adc_median'],bins=25 )
            ax.set_title('Chip %d'%(chip))
            ax.set_xlabel(r'$\Delta_{pedestal}$ [ADC counts]')
            plt.text( 0.7, 0.8, r'$\mu = %4.2f$ [ADC counts]'%(maxped-minped)['adc_median'].mean(),transform = ax.transAxes)
            plt.text( 0.7, 0.7, r'$\sigma = %4.2f$ [ADC counts]'%(maxped-minped)['adc_median'].std(),transform = ax.transAxes)
            plt.savefig("%s/delta_ped_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight')

            data = sel_data[ (sel_data['chip']==chip) & (sel_data['channeltype']==0) ]
            maxped = data.groupby(['channel']).max().reset_index()
            minped = data.groupby(['channel']).min().reset_index()
            x=[]
            y=[]
            for index,row in (maxped-minped).iterrows():
                #if row.adc_mean<2:continue
                x.append(index)
                y.append(row.adc_mean)
            fig, ax = plt.subplots(1,1,figsize=(16,9))
            plt.plot( x, y, marker='o')
            plt.title(r'$\Delta_{pedestal}$ vs channel ID, chip%d'%(chip))
            plt.xlabel(r'Channel id')
            plt.ylabel(r'$\Delta_{pedestal}$ [ADC counts]')
            plt.savefig("%s/delta_ped_vs_chanid_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 
        
        plt.close()

        # add summary information

    def addSummary(self):
        self._summary['pedestal_variation'] = {
            'rejection criteria': 'mean and sigma for pedestal variation'
        }
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','channel','half','channeltype','adc_mean','adc_stdd','Phase']].copy()
        for chip in range(nchip):
            data = sel_data[ (sel_data['chip']==chip) ]
            maxped = data[ data['channeltype']!=100 ].groupby(['channel','channeltype']).max().reset_index()
            minped = data[ data['channeltype']!=100 ].groupby(['channel','channeltype']).min().reset_index()
            mean_delta_ped = (maxped-minped)['adc_mean'].mean()
            mean_delta_noise = (maxped-minped)['adc_stdd'].mean()
            self._summary['adc_vs_phase']['chip%d' % chip] = {
                'mean_delta_ped': float(mean_delta_ped),
                'mean_delta_noise': float(mean_delta_noise),
            }
            
if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        phase_analyzer = phase_scan_analyzer(odir=odir)
        files = glob.glob(indir+"/phase_scan*.root")
        print(files)

        for f in files:
            phase_analyzer.add(f)
    
        phase_analyzer.mergeData()
        phase_analyzer.makePlots()
        phase_analyzer.addSummary()
        phase_analyzer.writeSummary()
    else:
        print("No argument given")
