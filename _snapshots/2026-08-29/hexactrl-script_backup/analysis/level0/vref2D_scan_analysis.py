from level0.analyzer import *
from scipy.optimize import curve_fit
import glob,itertools
import seaborn as sns 

class vref2D_scan_analyzer(analyzer):

    def makePlots(self):
        cmap = cm.get_cmap('YlOrRd')
        sel_data = self.data[['chip','channel','channeltype','adc_mean','adc_stdd','Inv_vref','Noinv_vref','half']].copy()
        df = sel_data.query('channeltype==0').groupby(['chip', 'half', 'Noinv_vref', 'Inv_vref'])[['adc_mean','adc_stdd']].mean()
        df.rename(columns={'adc_mean': 'pedestal', 'adc_stdd': 'noise'}, inplace=True)
        print(df)

        vmax_pedestal = np.nanpercentile(df['pedestal'], 98)
        vmax_noise = np.nanpercentile(df['noise'], 98)
        for chip in df.index.get_level_values('chip').unique():
            ########################
            ## pedestal vs vref 2D #
            ########################
            fig, axes = plt.subplots(1,2,figsize=(18,8),sharey=True)
            fig.suptitle('Vref 2D scan : pedestal')

            for half in 0, 1:
                ax = axes[half]
                plot = df.loc[chip, half].reset_index().pivot('Noinv_vref', 'Inv_vref', 'pedestal')
                h = sns.heatmap(plot, mask=(plot == 0), vmin=0, vmax=vmax_pedestal, ax=ax, cmap=cmap, linewidths=.5)
                h.collections[0].colorbar.set_label("Pedestal [ADC counts]",fontsize=15)
                ax.invert_yaxis()
                ax.tick_params(labelsize=12)
                cax = plt.gcf().axes[-1]
                cax.tick_params(labelsize=12)
                h.set_xlabel(r'Inv_vref',fontsize=15)
                h.set_ylabel(r'Noinv vref',fontsize=15)
                ax.set_title('Half %s' % half)
            plt.savefig('%s/pedestal2D_chip%d.png'%(self.odir,chip))
            

            
            #####################
            ## noise vs vref 2D #
            #####################
            fig, axes = plt.subplots(1,2,figsize=(18,8),sharey=True)
            fig.suptitle('Vref 2D scan : noise')

            for half in 0, 1:
                ax = axes[half]
                plot = df.loc[chip, half].reset_index().pivot('Noinv_vref', 'Inv_vref', 'noise')
                h = sns.heatmap(plot, mask=(plot == 0), vmin=0, vmax=vmax_noise, ax=ax, cmap=cmap, linewidths=.5)
                h.collections[0].colorbar.set_label("Noise [ADC counts]",fontsize=15)
                ax.invert_yaxis()
                ax.tick_params(labelsize=12)
                cax = plt.gcf().axes[-1]
                cax.tick_params(labelsize=12)
                h.set_xlabel(r'Inv_vref',fontsize=15)
                h.set_ylabel(r'Noinv vref',fontsize=15)
                ax.set_title('Half %s' % half)
            plt.savefig('%s/noise2D_chip%d.png'%(self.odir,chip))

if __name__ == "__main__":

    if len(sys.argv) == 2:
        indir = sys.argv[1]
        odir = sys.argv[1]
    elif len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]
    else:
        print("wrong arg list")

    vref2D_analyzer = vref2D_scan_analyzer(odir=odir)
    files = glob.glob(indir+"/*.root")
    print(files)
    
    for f in files:
        vref2D_analyzer.add(f)
 
    vref2D_analyzer.mergeData()
    vref2D_analyzer.makePlots()
