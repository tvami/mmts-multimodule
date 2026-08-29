from level0.analyzer import *
from scipy.optimize import curve_fit
import glob,yaml

class injection_run_analyzer(raw_analyzer):

    def makePlots(self,chip_params):
        data = self.data
    
        nchip = len( data.groupby('chip').nunique() )
        
        injectedChannels = chip_params['injectedChannels']
        gain = chip_params['Inj_gain']
        calibdac = chip_params['Calib_dac']
        global_tot_trh = chip_params['Tot_vref']
        global_toa_trh = chip_params['Toa_vref']

        cmap = cm.get_cmap('viridis')
        cmap.colors[0] = [1,1,1]
        
        for chip in data.groupby('chip')['chip'].mean():
            chip_data = data[ (data['chip']==chip) & (data['channel']<36) ].copy() # only full channels will be shown
            chip_data['channelID'] = chip_data.apply(lambda x : x.channel + x.half*36,axis=1 ) 
            
            f, ax = plt.subplots(figsize=(12, 9))
            H, xedges, yedges = np.histogram2d( x=chip_data['channelID'], y=chip_data['adc'], bins=(72,100) )
            H = H.T
            X, Y = np.meshgrid(xedges, yedges)
            ax.pcolormesh(X,Y,H,cmap=cmap)
            for tick in ax.xaxis.get_major_ticks():
                tick.label.set_fontsize(15) 
            for tick in ax.yaxis.get_major_ticks():
                tick.label.set_fontsize(15) 
            plt.xlabel(r'Channel ',fontsize=20)
            plt.ylabel(r'ADC',fontsize=20)

            if gain==0 : 
                plt.title('Chip %d, lowrange, calib dac %d in channels %s'%(chip,calibdac,injectedChannels))
            else:
                plt.title('Chip %d, highrange, calib dac %d in channels %s'%(chip,calibdac,injectedChannels))
            plt.savefig('%s/adc_vs_channel_chip%d.png'%(self.odir,chip))
            plt.cla()
            
            H, xedges, yedges = np.histogram2d( x=chip_data['channelID'], y=chip_data['tot'], bins=(72,100) )
            H = H.T
            X, Y = np.meshgrid(xedges, yedges)
            ax.pcolormesh(X,Y,H,cmap=cmap)
            for tick in ax.xaxis.get_major_ticks():
                tick.label.set_fontsize(15) 
            for tick in ax.yaxis.get_major_ticks():
                tick.label.set_fontsize(15) 
            plt.xlabel(r'Channel ',fontsize=20)
            plt.ylabel(r'ToT',fontsize=20)

            if gain==0 : 
                plt.title('Chip %d, lowrange, calib dac %d in channels %s (ToT thr:%d)'%(chip,calibdac,injectedChannels,global_tot_trh))
            else:
                plt.title('Chip %d, highrange, calib dac %d in channels %s (ToT thr:%d)'%(chip,calibdac,injectedChannels,global_tot_trh))
            plt.savefig('%s/tot_vs_channel_chip%d.png'%(self.odir,chip))
            plt.cla()

            H, xedges, yedges = np.histogram2d( x=chip_data['channelID'], y=chip_data['toa'], bins=(72,100) )
            H = H.T
            X, Y = np.meshgrid(xedges, yedges)
            ax.pcolormesh(X,Y,H,cmap=cmap)
            for tick in ax.xaxis.get_major_ticks():
                tick.label.set_fontsize(15) 
            for tick in ax.yaxis.get_major_ticks():
                tick.label.set_fontsize(15) 
            plt.xlabel(r'Channel ',fontsize=20)
            plt.ylabel(r'ToA',fontsize=20)

            if gain==0 : 
                plt.title('Chip %d, lowrange, calib dac %d in channels %s (Toa thr:%d)'%(chip,calibdac,injectedChannels,global_toa_trh))
            else:
                plt.title('Chip %d, highrange, calib dac %d in channels %s (Toa thr:%d)'%(chip,calibdac,injectedChannels,global_toa_trh))
            plt.savefig('%s/toa_vs_channel_chip%d.png'%(self.odir,chip))
            plt.cla()

            plt.clf()
        plt.close()

if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        run_analyzer = injection_run_analyzer(odir=odir)
        files = glob.glob(indir+"/injection_run*.raw")
        print(files)
        for f in files:
            run_analyzer.add(f)
        run_analyzer.mergeData()

        metayamlfile = glob.glob(indir+"/injection_run*.yaml")[0]
        with open(metayamlfile) as fin:
            metayaml = yaml.safe_load(fin)

        run_analyzer.makePlots(metayaml['chip_params'])

    else:
        print("No argument given")
