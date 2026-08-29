from level0.analyzer import *
from scipy.optimize import curve_fit
import glob

class tdc_threshold_scan_analyzer(analyzer):

    def makePlots(self):
        cmap = cm.get_cmap('cool')
        cmcmap = cm.get_cmap('Dark2')
        nchip = len( self.data.groupby('chip').nunique() )        

        sel_data = self.data[['chip','channel','half','channeltype','adc_mean','adc_stdd','Toa_vref']].copy()

        for chip in range(nchip):

            ####################################
            ## plot of pedestal vs tdc_threshold: 
            ####################################
            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            ax=axes[0]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==0) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_mean'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_mean'], c=inv, cmap=cmap)
            ax.set_title('First half')
            ax.set_xlabel(r'Toa_vref')
            ax.set_ylabel(r'Pedestal [ADC counts]')

            ax=axes[1]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==1) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_mean'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_mean'], c=inv, cmap=cmap)
            ax.set_title('Second half')
            ax.set_xlabel(r'Toa_vref')

            plt.savefig("%s/pedestal_vs_Toa_vref_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight')

            ####################################
            ## plot of noise vs tdc_threshold: 
            ####################################
            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            ax=axes[0]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==0) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_stdd'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_stdd'], c=inv, cmap=cmap)
            ax.set_title('First half')
            ax.set_xlabel(r'Toa_vref')
            ax.set_ylabel(r'Noise [ADC counts]')
            # ax.set_yscale('log')
            # ax.set_ylim(0,10)

            ax=axes[1]
            data = sel_data[ (sel_data['chip']==chip) & (sel_data['half']==1) ]
            chan_data = data[ (data['channeltype']<=1) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_stdd'], c=inv)
            
            chan_data = data[ (data['channeltype']==100) ].copy()
            u, inv = np.unique(chan_data.channel.values, return_inverse=True)
            ax.scatter(chan_data['Toa_vref'], chan_data['adc_stdd'], c=inv, cmap=cmap)
            ax.set_title('Second half')
            ax.set_xlabel(r'Toa_vref')
            # ax.set_yscale('log')
            # ax.set_ylim(0,10)

            plt.savefig("%s/noise_vs_Toa_vref_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight')
            ax.set_yscale('log')
            plt.savefig("%s/noise_vs_Toa_vref_chip%d_log.png"%(self.odir,chip),format='png',bbox_inches='tight')
        plt.close()


if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        tdc_threshold_analyzer = tdc_threshold_scan_analyzer(odir=odir)
        files = glob.glob(indir+"/tdc_threshold_scan*.root")

        for f in files:
            tdc_threshold_analyzer.add(f)

        tdc_threshold_analyzer.mergeData()
        tdc_threshold_analyzer.makePlots()

    else:
        print("No argument given")
