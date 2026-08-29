from level0.analyzer import *
import yaml
import glob
from scipy.optimize import curve_fit
from nested_dict import nested_dict
import more_itertools as mit
import argparse 

def tot_func():
    alpha*x*500/4096+b

class injection_scan_analyzer(analyzer):

    def fit(self,sel,var='adc_mean'):
        x0 = self.data[sel]['Calib']
        y0 = self.data[sel][var]
        if len(x0)>2:
            popt, pcov = curve_fit(lambda x,a,b:a*x*500/4096+b, x0, y0, p0=[0.6,y0.min()])
        else:
            popt = [1,0]

        return popt[0],popt[1]
    
    def adcrange_from_residuals(self,sel,alpha,beta):
        tmp = self.data[sel].copy()
        tmp = tmp[['chip','channel','Calib','adc_mean']].copy()
        tmp.sort_values(by=['adc_mean'],ignore_index=True)
        tmp['res'] = tmp.apply(lambda x: (x.adc_mean-(x.Calib*alpha*500/4096+beta))/(x.Calib*alpha*500/4096+beta) ,axis=1)
        tmp['fC'] = tmp.apply(lambda x: x.Calib*500/4096, axis=1)
        tmp = tmp.sort_values(by=['Calib'],ignore_index=True)

        alist = list(tmp[ tmp['res']<-.02 ].index)
        alist = [list(group) for group in mit.consecutive_groups(alist)]

        first=[]
        for i in alist:
            if len(i)>2:
                first=i
                break

        adcrange = tmp.iloc[first[0]-1]
        return adcrange["Calib"]*500/4096

    def makePlots(self):
        cmap = mpl.colormaps.get_cmap('tab20')

        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = self.data[['chip','channel','channeltype','Calib','adc_median','toa_median','tot_median','toa_stdd','toa_efficiency','tot_efficiency','injectedChannels']].copy()
        injectedChannels = sel_data['injectedChannels'].to_list()
        injectedChannels = [ ch for channels in injectedChannels for ch in channels ]
        injectedChannels = set( injectedChannels )
        
        sel_data = sel_data[ (sel_data['channel'].isin(injectedChannels)) & (sel_data['channeltype']==0) ]#& (sel_data['tot_median']<4000) ]
        sel_data = sel_data[ ~sel_data['channel'].isin(unconnectedChannels) ]
        sel_data = sel_data.sort_values(by=['Calib'],ignore_index=True)

        
        # offenders = sel_data[ (sel_data.toa_median > 0) & (sel_data.Calib < 800) ]
        # print(
        #     offenders[ ['chip', 'channel'] ].drop_duplicates().sort_values( by=['chip', 'channel'], ignore_index=True)
        # )

        # print( injectedChannels )
        
        # print(sel_data.describe())
        for chip in sel_data['chip'].unique():
            ###########################################################
            ## let's plot ADC vs. injection for all injected channels: 
            ###########################################################
            chip_data = sel_data[ sel_data['chip']==chip ]
            print(chip_data)

            varlist ={
                'adc':'adc_median',
                'toa':'toa_median',
                'tot':'tot_median',
                'toa_stdd':'toa_stdd',
                'eff_toa':'toa_efficiency',
                'eff_tot':'tot_efficiency'
            }
            
            for var in varlist:
                fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=True)
                
                axes[0].set_ylabel(f'{var.upper()} [ADC counts]')

                for ax in axes:
                    # ax.set_yscale('log')                
                    ax.set_xlabel(r'CalibDAC')
                    ax.xaxis.grid(True)
                    ax.yaxis.grid(True)

                axes[0].set_title(f'chip{chip}, first half')
                axes[1].set_title(f'chip{chip}, second half')
                chanColor=0
                for ch in injectedChannels:
                    half_data = chip_data.query(f'channel=={ch}').sort_values('Calib')
                    #half_data = half_data.query(f'{varlist[var]}>0')
                    if ch<36:
                        ax=axes[0]
                    else:
                        ax=axes[1]
                    if len(half_data):
                        ax.plot( half_data['Calib'], half_data[varlist[var]], color=cmap((ch%36)%20), marker='o',label="chan%d"%ch)
                for half in [0,1]:
                    h,l=axes[half].get_legend_handles_labels()
                    axes[half].legend(handles=h,labels=l,loc='lower right',ncol=2,fontsize=8)
                
                plt.savefig(f'{self.odir}/{var}_injection_scan_chip{chip}.png', format='png', bbox_inches='tight') 
                
                plt.close()

        return


    def toaTurnOnPlot(self):
        unconnectedChannels=[8,17,18,27,
                             36+8,36+17,36+18,36+27]
        sel_data = self.data[['chip','channel','channeltype','Calib','toa_efficiency','tot_efficiency','injectedChannels']].copy()
        injectedChannels = sel_data['injectedChannels'].iloc[0].to_list()
        sel_data = sel_data[ (sel_data['channel'].isin(injectedChannels)) & (sel_data['channeltype']==0) ]
        sel_data = sel_data[ ~sel_data['channel'].isin(unconnectedChannels) ]
        sel_data = sel_data.sort_values(by=['Calib'],ignore_index=True)

        for chip in sel_data.groupby('chip')['chip'].mean():
            ###########################################################
            ## let's plot ADC vs. injection for all injected channels: 
            ###########################################################
            chip_data = sel_data[ sel_data['chip']==chip ]


            varlist ={
                'toa':'toa_efficiency',
                'tot':'tot_efficiency'
            }            

            for var in varlist:
                turnOnList = {0:[], 1:[]}
                for ch in injectedChannels:
                    df_chn = chip_data.query(f'channel=={ch}').sort_values('Calib')
                    sel0 = df_chn[varlist[var]]>0.4
                    sel1 = ~sel0
                    if sel0.any() and sel1.any():
                        turnOnList[int(ch/36)].append( int(df_chn[sel0]["Calib"].min())*500/4096. )
                
                turnOnList = [ np.array(turnOnList[0]), np.array(turnOnList[1]) ] 
                print(chip,turnOnList)
                med0 = turnOnList[0].mean() #np.quantile(turnOnList[0],0.5,interpolation='lower') if len(turnOnList[0])>0 else 4000 
                med1 = turnOnList[1].mean() #np.quantile(turnOnList[1],0.5,interpolation='lower') if len(turnOnList[1])>0 else 4000  

                fig, ax = plt.subplots(figsize=(16,9))
                ax.set_xlabel(f'{var.upper()} threshold [fC]')
                ax.set_ylabel(f'# channels')
                ax.xaxis.grid(True)
                ax.set_title('Chip %d'%(chip))

                histos = ax.hist( turnOnList, alpha=0.8 ,label=['half 0','half 1'],color=['orange','skyblue'])
                h,l=ax.get_legend_handles_labels()
                ax.legend(handles=h,labels=l,loc='upper left')
                plt.text( 0.02, 0.7, r'$\bar{Thr} = %4.1f$ [fC]'%med0,transform = ax.transAxes,color='orange')
                plt.text( 0.02, 0.6, r'$\bar{Thr} = %4.1f$ [fC]'%med1,transform = ax.transAxes,color='skyblue')
                plt.savefig(f'{self.odir}/{var}_threshold_chip{chip}.png',format='png',bbox_inches='tight')
                plt.cla()
                plt.clf()
            
        return

    def totCalib(self):
        data = self.data[['chip','channel','channeltype','Calib','tot_median','injectedChannels']].copy()
        all_rows=[]
        injectedChannels = data['injectedChannels'].iloc[0].to_list()
        for chip in data['chip'].unique():
            for channel in injectedChannels:
                sel = data.chip==int(chip)
                sel &= data.channeltype==0
                sel &= data.channel==int(channel)

                chan_data = data[sel]
                chan_data.sort_values(by=['Calib'],ignore_index=True)
                threshold = chan_data[chan_data.tot_median>0]['Calib'].iloc[0]*500/4096.
                
                sel &= data.tot_median>50
                sel &= data.Calib>0
                alpha,beta = self.fit(sel,var='tot_median')

                tot_to_fC = float(1/alpha)
                tot_pedestal = beta
                all_rows.append([chip,channel,0,tot_to_fC,tot_pedestal,threshold])
                #print(chip,channel,params)
        calib = pd.DataFrame(all_rows, columns=['chip','channel','channeltype','tot_to_fC','tot_pedestal','threshold'])
        calibfile = calib.to_hdf(f'{self.odir}/tot_calib.h5', key='tot_calib', mode='w')
        return


    def adcCalib(self):
        data = self.data[['chip','channel','channeltype','Calib','adc_mean','injectedChannels']].copy()
        injectedChannels = data['injectedChannels'].iloc[0].to_list()
        all_rows=[]
        for chip in data['chip'].unique():
            for ch in injectedChannels:
                sel = data.chip==int(chip)
                sel &= data.channeltype==0
                sel &= data.channel==int(ch)
                sel &= data.adc_mean<500
                sel &= data.Calib>0
                alpha,beta = self.fit(sel)
                adcrange = 0
                if alpha!=1 and alpha>1e-3 and beta!=0:
                    sel = data.chip==int(chip)
                    sel &= data.channeltype==0
                    sel &= data.channel==int(ch)
                    adcrange = self.adcrange_from_residuals(sel,alpha,beta)
                    # adcrange = min(adcrange,float((1023-beta)/alpha))
                adc_to_fC = float(1/alpha)
                pedestal = float(beta)
                all_rows.append([chip,ch,0,adc_to_fC,pedestal,adcrange])
        calib = pd.DataFrame(all_rows, columns=['chip','channel','channeltype','adc_to_fC','pedestal','range'])
        calibfile = calib.to_hdf(f'{self.odir}/adc_calib.h5', key='adc_calib', mode='w')
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

    ana = injection_scan_analyzer(odir=odir)
    files = glob.glob(indir+"/*.root")
    
    try:
        ana.mergeData()
    except:
        ana.altMergeData()
    ana.makePlots()
    ana.toaTurnOnPlot()
    # ana.addSummary()
    # ana.writeSummary()
    ana.adcCalib()
    ana.totCalib()

    adc = pd.read_hdf(f'{odir}/adc_calib.h5')
    tot = pd.read_hdf(f'{odir}/tot_calib.h5')

    calib = pd.concat([adc,tot],axis=1)
    calib = calib.loc[:, ~calib.columns.duplicated()]
    calib['MultFactor'] = calib.apply(lambda x: x.tot_to_fC/x.adc_to_fC,axis=1)
    print(calib)
    calib.to_hdf(f'{odir}/calib.h5', key='calib', mode='w')
