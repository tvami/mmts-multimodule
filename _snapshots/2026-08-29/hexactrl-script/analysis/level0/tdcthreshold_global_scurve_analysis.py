from level0.analyzer import *
from scipy.optimize import curve_fit
import glob

class tdcthreshold_global_scurve_analyzer(analyzer):
    def makePlots(self, injectedChannels):
        nchip = len( self.data.groupby('chip').nunique() )        
        cmap = cm.get_cmap('viridis')

        sel_data = self.data[['chip','half','channel','channeltype','Calib_dac','toa_efficiency','tot_efficiency','Toa_vref','Tot_vref']].copy()
        sel_data = sel_data.sort_values(by=['Calib_dac'],ignore_index=True)
        
        h0inj = [ch for ch in injectedChannels if ch < 36]
        h1inj = [ch for ch in injectedChannels if ch >= 36]

        for chip in sel_data.groupby('chip')['chip'].mean():
            ###########################################################
            ## let's plot ADC vs. injection for all injected channels: 
            ###########################################################
            chip_data = sel_data[ sel_data['chip']==chip ]

            toa_medians = chip_data[ (chip_data['channel'].isin(injectedChannels)) & (chip_data['channeltype']==0) ].groupby(['half','Toa_vref']).mean().reset_index()
            tot_medians = chip_data[ (chip_data['channel'].isin(injectedChannels)) & (chip_data['channeltype']==0) ].groupby(['half','Tot_vref']).mean().reset_index()
            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            for half in range(2):
                ax=axes[half]
                half_data = toa_medians[ toa_medians['half']==half ]
                ax.plot(half_data['Toa_vref'], half_data['toa_efficiency'], color='blue',marker='o')
                ax.set_title('Half %d'%(half))
                ax.set_ylim(0,1)
                ax.set_xlabel(r'ToA threshold [DAC counts] ')
            axes[0].set_ylabel(r'Average ToA efficiency')
            plt.savefig("%s/toa_scurve_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 

            plt.cla()
            plt.clf()
            
            fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
            for half in range(2):
                ax=axes[half]
                half_data = toa_medians[ toa_medians['half']==half ]
                ax.plot(half_data['Tot_vref'], half_data['tot_efficiency'], color='blue',marker='o')
                ax.set_title('Half %d'%(half))
                ax.set_xlabel(r'ToT threshold [DAC counts] ')
                ax.set_ylim(0,1)
            axes[0].set_ylabel(r'Average ToT efficiency')
            plt.savefig("%s/tot_scurve_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 

            plt.cla()
            plt.clf()

            plt.close()
    def fit(self,data):
        pass

if __name__ == "__main__":

	if len(sys.argv) == 3:
		indir = sys.argv[1]
		odir = sys.argv[2]

		ana = tdcthreshold_global_scurve_analyzer(odir=odir)
		files = glob.glob(indir+"/*.root")

		for f in files:
			ana.add(f)

		ana.mergeData()
		injectedChannels = [i*10 for i in range(8)]

		ana.makePlots(injectedChannels)

	else:
		print("No argument given")
