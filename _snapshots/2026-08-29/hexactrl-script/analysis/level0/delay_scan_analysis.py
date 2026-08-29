import json,glob
from time import sleep
from level0.analyzer import *

plt.rcParams.update({'font.size': 15})

class delay_scan_analyzer(analyzer):
    def __init__(self, odir="./"):
        super().__init__(odir=odir, treename='delayScanTree')
        self.links = []
        with open("%s/initial_full_config.yaml"%odir) as fin:
            config = yaml.safe_load(fin)
        # with open("data/testWIP/pedestal_run/run_20220124_142633/initial_full_config.yaml") as fin:
        #     config = yaml.safe_load(fin)
        
        for link in config['daq']['elinks_daq']:
            self.links.append( b'link_capture_daq.'+link['name'].encode("utf-8") )
        for link in config['daq']['elinks_trg']:
            self.links.append( b'link_capture_trg.'+link['name'].encode("utf-8") )
    
    def __del__(self):
        pass 

    def mergeData(self):
        fname=f"{self.odir}/delayScan0.root"
        self.data = reader(fname, treename=self._treename, branches=self._branches).df
        
    def makePlots(self):
        nqualSummary = {}
        print(self.links)
        for link in self.links :
            data = self.data[ self.data['link']==link ]

            imax = 0
            wrun = 0

            nqual = dict(ngood=0, nbad=0, nturnon=0, wmax=0)
            for k, r in data.iterrows():
                if r['errorCount']<=1 and r['alignedCount']==128:
                    wrun+=1
                    nqual['ngood']+=1
                else:
                    if wrun>nqual['wmax']:
                        nqual['wmax'] = wrun
                        imax = r['idelay']
                    wrun = 0
                    if r['errorCount']==255 and r['alignedCount']==0: 
                        nqual['nbad']+=1
                    else: 
                        nqual['nturnon']+=1
        
            fig= plt.figure(figsize=(9,6))
            ax=fig.add_subplot(1,1,1)
        
            plt.xlim(0,512)
            plt.ylim(0,270)
            plt.scatter(data['idelay'], data['errorCount'], color='black', s=15, label=r'Number of errors')
            plt.scatter(data['idelay'], data['alignedCount'], color='red', s=15, label=r'Number of success')

            plt.xlabel(r'iDelay',fontsize=15)
            plt.ylabel(r'#',fontsize=15)

            h,l=ax.get_legend_handles_labels() # get labels and handles from ax1
            wmax = nqual['wmax']
            arrcenter = imax-wmax/2
            ax.arrow(x=arrcenter, y=50, dx= wmax/2, dy=0, width=2, length_includes_head=True, color="green");
            ax.arrow(x=arrcenter, y=50, dx=-wmax/2, dy=0, width=2, length_includes_head=True, color="green");
            ax.text(x=arrcenter-30, y=55, s="w = %d"%(wmax), fontsize=15)
            ax.text(x=435, y=280, font='monospace', 
                    s="%-7s = %3d\n%-7s = %3d \n%-7s = %3d" % ('nGood', nqual['ngood'], 'nBad', nqual['nbad'], 'nTurnon', nqual['nturnon']))
            ax.legend(handles=h,labels=l,loc='upper left',fontsize=15)

            title = str(link).split("b'")[1].split("'")[0]
            plt.title(title)
            title = str(link).split("b'")[1].split("'")[0]
            plt.savefig("%s/%s.png"%(self.odir,title),format='png',bbox_inches='tight') 
            plt.close()
            nqualSummary[title] = nqual
            
        with open("%s/summary.json"%(self.odir), 'w') as jfile:
            json.dump(nqualSummary, jfile)

        
    
        
if __name__ == "__main__":

    if len(sys.argv) == 3:
        indir = sys.argv[1]
        odir = sys.argv[2]

        delay_analyzer = delay_scan_analyzer(odir=odir)
        files = glob.glob(indir+"/*.root")
        delay_analyzer.mergeData()
        delay_analyzer.makePlots()
    else:
        print("No argument given")
