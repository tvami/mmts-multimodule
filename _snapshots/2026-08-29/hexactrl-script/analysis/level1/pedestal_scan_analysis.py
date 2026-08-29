import os,glob,yaml
import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 114
import matplotlib.pyplot as plt
import matplotlib.cm as cm

import level0.pedestal_scan_analysis as analyzer
from summaryWriter import *

def run(inputDir,outputDir,reset):
    chips = glob.glob(inputDir+"/*")

    nbadchannels=[]
    nbadrefdacch=[]
    ntotalbadchs=[]
    slopes=[]
    offsets=[]
    for chip in chips:
        if chip.split(inputDir+"/")[1].isdigit()==False:
            continue

        run = glob.glob(chip+"/pedestal_scan/*")
        if len(run)!=1 : 
            print("WRONG chip : %s"%chip)
            continue
        run=run[0]
        if reset==True or os.path.isfile(run+"/analysis_summary.yaml")==False:
            ped_scan_analyzer = analyzer.pedestal_scan_analyzer(odir=run)
            writeSummary(odir=run,analyzer=ped_scan_analyzer)
            fitParams = pd.read_hdf(run+'/pedestal_scan.h5','pedestal_scan')
            slopes.extend( fitParams['alpha'] )
            offsets.extend( fitParams['beta'] )
            
        with open("%s/analysis_summary.yaml"%run) as fin:
            summary = yaml.safe_load(fin)
            summary_badchan = summary["bad_channels_pedestal"]
            summary_badrefdacchan = summary["bad_channels_ref_dac"]
            nbadchannels.append( summary_badchan['chip0']['total'] )
            nbadrefdacch.append( summary_badrefdacchan['chip0']['total'] )
            ntotalbadchs.append( len(list( set(summary_badchan['chip0']['ch']) | set(summary_badrefdacchan['chip0']['ch'] ) )) +
                                 len(list( set(summary_badchan['chip0']['cm']) | set(summary_badrefdacchan['chip0']['cm'] ) )) +
                                 len(list( set(summary_badchan['chip0']['calib']) | set(summary_badrefdacchan['chip0']['calib'] ) )) )


    fig, axes = plt.subplots(1,2,figsize=(16,9),sharey=False)
    ax1=axes[0]
    ax1.hist(slopes)
    ax1.set_title('Slope of pedestal scan')
    plt.xlabel(r'Slope')
    plt.ylabel(r'# channels')

    ax2=axes[1]
    ax2.hist(offsets)
    ax2.set_title('Offset of pedestal scan')
    plt.xlabel(r'Offset')
    plt.ylabel(r'# channels')
    plt.savefig("%s/pedestal_scan_fitparams.png"%(outputDir),format='png',bbox_inches='tight')

    plt.cla()
    plt.clf()

    badchannelhists = []
    labels = []
    badchannelhists.append( nbadchannels )
    labels.append('Bad channels (1st criteria)')
    badchannelhists.append( nbadrefdacch )
    labels.append('Bad channels (2nd criteria)')
    badchannelhists.append( ntotalbadchs )
    labels.append('Total')

    fig, ax = plt.subplots(1,1,figsize=(16,9))
    ax.hist( badchannelhists, label=labels )
    ax.set_xlabel(r'Number of bad channels')
    ax.set_ylabel(r'# Chips')
    ax.set_yscale('log')
    h,l=ax.get_legend_handles_labels() # get labels and handles from ax1
    ax.legend(handles=h,labels=l,loc='upper right',ncol=1)
    

    plt.savefig(outputDir+"/pedestal_scan_summary.png",format='png',bbox_inches='tight')    
    plt.close()
        
if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    
    parser.add_option("-i", "--inputDir", dest="inputDir", default="data", type="string",  
                      help="input directory with the all DUT data")

    parser.add_option("-o", "--outputDir", dest="outputDir", default=None,
                      help="ouput directory for the figures")

    parser.add_option("-r", "--reset",
                      action="store_true", dest="reset", default="False",
                      help="flag to set to withdraw the analysis_summary.yaml files and re-run from scratch")
    
    (options, args) = parser.parse_args()
    print(options)
    

    odir=options.inputDir
    if None!=options.outputDir:
        odir=options.outputDir
    run(options.inputDir,odir,options.reset)
