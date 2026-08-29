import argparse
from level0.analyzer import *
import yaml
import glob

class scurve_2D_analyzer(analyzer):
    def makePlots(self):
        nchip = len( self.data.groupby('chip').nunique() )        
        cmap = cm.get_cmap('viridis')
        
        sel_data = self.data[['chip','channel','channeltype','Calib','adc_median','toa_median','tot_median','toa_efficiency','tot_efficiency','injectedChannels','Toa_vref','Tot_vref']].copy()
        sel_data = sel_data[ (sel_data['channel'].isin(sel_data['injectedChannels'])) & (sel_data['channeltype']==0) ]
        sel_data = sel_data.sort_values(by=['Toa_vref','Calib'],ignore_index=True)

        #chipid   = []

        for chip in sel_data.groupby('chip')['chip'].mean():

            df = sel_data.query('chip==%d' % chip)
            df = df.query('channeltype==0')
            scurve_toa = {}
            scurve_tot = {}
            zcurve = {}
            for ch in df.groupby('injectedChannels')['injectedChannels'].mean():
                df_chn = df.query('channel==%s & injectedChannels==%s' % (ch,ch)).sort_values('Calib')
                
                scurve_toa[ch] = { 'calib':[], 'thr':[], 'toa_vref':[] }
                for toavref in df.groupby('Toa_vref')['Toa_vref'].mean():
                    sel = df_chn['toa_efficiency']>0.5
                    sel &= df_chn['Toa_vref']==toavref
                    if sel.any():
                        scurve_toa[ch]['calib'].append(df_chn[sel].iloc[0]['Calib'])
                        scurve_toa[ch]['thr'].append(df_chn[sel].iloc[0]['Calib']*500/4096)
                        scurve_toa[ch]['toa_vref'].append(toavref)

                scurve_tot[ch] = { 'calib':[], 'thr':[], 'tot_vref':[] }
                for totvref in df.groupby('Tot_vref')['Tot_vref'].mean():
                    sel = df_chn['tot_efficiency']>0.5
                    sel &= df_chn['Tot_vref']==totvref
                    if sel.any():
                        scurve_tot[ch]['calib'].append(df_chn[sel].iloc[0]['Calib'])
                        scurve_tot[ch]['thr'].append(df_chn[sel].iloc[0]['Calib']*500/4096)
                        scurve_tot[ch]['tot_vref'].append(totvref)

                zcurve[ch] = { 'calib':[], 'thr':[], 'toa_vref':[] }
                for calib in df.groupby('Calib')['Calib'].mean():
                    sel = df_chn['toa_efficiency']>0.5
                    sel &= df_chn['Calib']==calib
                    if sel.any():
                        zcurve[ch]['calib'].append(calib)
                        zcurve[ch]['thr'].append(calib*500/4096)
                        zcurve[ch]['toa_vref'].append(int(df_chn[sel]["Toa_vref"].max()))

            
            fig, ax = plt.subplots(1,1,figsize=(16,9))
            # print(scurve_toa)
            for ch in scurve_toa:
                ax.plot(scurve_toa[ch]['toa_vref'], scurve_toa[ch]['thr'],marker='o',color=cmap(ch/72.),label=r'Channel %d'%(ch))
            ax.xaxis.grid(True)
            ax.yaxis.grid(True)
            ax.set_xlabel(r'Toa_vref [DAC counts]')
            ax.set_ylabel(r'Toa threshold [fC]')
            h,l=ax.get_legend_handles_labels()
            ax.legend(handles=h,labels=l,loc='upper left',ncol=2)
            plt.savefig("%s/scurve_2D_toa_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 

            fig, ax = plt.subplots(1,1,figsize=(16,9))
            # print(scurve_tot)
            for ch in scurve_tot:
                ax.plot(scurve_tot[ch]['tot_vref'], scurve_tot[ch]['thr'],marker='o',color=cmap(ch/72.),label=r'Channel %d'%(ch))
            ax.xaxis.grid(True)
            ax.yaxis.grid(True)
            ax.set_xlabel(r'Tot_vref [DAC counts]')
            ax.set_ylabel(r'Tot threshold [fC]')
            h,l=ax.get_legend_handles_labels()
            ax.legend(handles=h,labels=l,loc='upper left',ncol=2)
            plt.savefig("%s/scurve_2D_tot_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 

            
            fig, ax = plt.subplots(1,1,figsize=(16,9))
            # print(zcurve)
            for ch in zcurve:
                ax.plot(zcurve[ch]['thr'], zcurve[ch]['toa_vref'],marker='o',color=cmap(ch/72.),label=r'Channel %d'%(ch))
            ax.xaxis.grid(True)
            ax.yaxis.grid(True)
            ax.set_ylabel(r'Toa threshold [DAC counts]')
            ax.set_xlabel(r'Injection DAC [fC]')
            h,l=ax.get_legend_handles_labels()
            ax.legend(handles=h,labels=l,loc='upper left',ncol=2)
            plt.savefig("%s/zcurve_2D_toa_chip%d.png"%(self.odir,chip),format='png',bbox_inches='tight') 

            plt.close()


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
        
    ana = scurve_2D_analyzer(odir=odir)
    files = glob.glob(indir+"/*.root")
        
    for f in files:
        ana.add(f)
        
    ana.mergeData()
    ana.makePlots()
