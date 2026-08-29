import os,glob,yaml
import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 114
import matplotlib.pyplot as plt
import matplotlib.cm as cm

import level0.injection_scan_analysis as analyzer
from summaryWriter import *

def run(inputDir,outputDir,reset):
    chips = glob.glob(inputDir+"/*")

    nbadchannelsadc=[]
    nbadchannelstoa=[]
    nbadchannelstot=[]
    nbadchannelsmaxadc=[]  ###add
    ntotalbadchs=[]
    ntotalbadchstdc=[]
    index=0
    for chip in chips:
        #if index>10:
        #    break
        #index=index+1
        #print (chip)
        #print (chip.split(inputDir+"/"))
        if chip.split(inputDir+"/")[1].isdigit()==False:
            continue
        
        run = glob.glob(chip+"/injection_scan/*")
        if len(run)<2 : 
            print("WRONG chip : %s"%chip)
            continue
        run = sorted(run)[1]
        # run=run[0]
        if reset==True or os.path.isfile(run+"/analysis_summary.yaml")==False:
            ## instead of hardcoding injectedChannels we should save the table in the yaml files (instead of many useless params) and parse one of them here
            injectedChannels = [i for i in range(72)]
            scan_analyzer = analyzer.injection_scan_analyzer(odir=run,injectedChannels=injectedChannels)
            writeSummary(odir=run,analyzer=scan_analyzer)
            
        with open("%s/analysis_summary.yaml"%run) as fin:
            summary = yaml.safe_load(fin)
            summary_badchan_adc = summary["bad_channels_adc"]
            summary_badchan_toa = summary["bad_channels_toa"]
            summary_badchan_tot = summary["bad_channels_tot"]
            summary_badchan_max_adc = summary["bad_channels_max_adc"]
            nbadchannelsadc.append( summary_badchan_adc['chip0']['total'] )
            nbadchannelsmaxadc.append( summary_badchan_max_adc['chip0']['total'] )
            nbadchannelstot.append( summary_badchan_tot['chip0']['total'] )
            nbadchannelstoa.append( summary_badchan_toa['chip0']['total'] )
            ntotalbadchs.append( len(list( set(summary_badchan_adc['chip0']['ch'])    | set(summary_badchan_max_adc['chip0']['ch'])  )) +
                                 len(list( set(summary_badchan_adc['chip0']['cm'])    | set(summary_badchan_max_adc['chip0']['cm'] ))) +
                                 len(list( set(summary_badchan_adc['chip0']['calib']) | set(summary_badchan_max_adc['chip0']['calib'] ) )) )
            # we used the intersection for the TDCs because we have seen weird toa behavior (not always reproducible) without tot issue
            ntotalbadchstdc.append( len( set.intersection(set(summary_badchan_toa['chip0']['ch'])    , set(summary_badchan_tot['chip0']['ch']) )) +
                                    len( set.intersection(set(summary_badchan_toa['chip0']['cm'])    , set(summary_badchan_tot['chip0']['cm']) )) +
                                    len( set.intersection(set(summary_badchan_toa['chip0']['calib']) , set(summary_badchan_tot['chip0']['calib']) )) )
            # if ntotalbadchs[len(ntotalbadchs)-1]>5:
            #     print(chip.split('data/')[1])
    badchannelhists = []
    labels = []
    badchannelhists.append( nbadchannelsadc )
    labels.append('# of bad channels (ADC criterion)')
    badchannelhists.append( nbadchannelstoa )
    labels.append('# of bad channels (TOA criterion)')
    badchannelhists.append( nbadchannelstot )
    labels.append('# of bad channels (TOT criterion)')
    badchannelhists.append( nbadchannelsmaxadc )
    labels.append('# of bad channels (MAX ADC criterion)')

    fig, ax = plt.subplots(1,2,figsize=(18,9))
    ax[0].hist( badchannelhists, label=labels )
    ax[0].set_xlabel(r'# of bad channels')
    ax[0].set_ylabel(r'# Chips')
    ax[0].set_yscale('log')
    h,l=ax[0].get_legend_handles_labels() # get labels and handles from ax1
    ax[0].legend(handles=h,labels=l,loc='upper right',ncol=1,fontsize=15)
    
    totalbadchannelhists = []
    totallabels = []
    totalbadchannelhists.append( ntotalbadchs )
    totallabels.append('Total # of bad channels (based on ADCs)')
    totalbadchannelhists.append( ntotalbadchstdc )
    totallabels.append('Total # of bad channels (based on TDCs)')

    ax[1].hist( totalbadchannelhists, label=totallabels )
    ax[1].set_xlabel(r'Total # of bad channels')
    ax[1].set_ylabel(r'# Chips')
    ax[1].set_yscale('log')
    h,l=ax[1].get_legend_handles_labels() # get labels and handles from ax1
    ax[1].legend(handles=h,labels=l,loc='upper right',ncol=1,fontsize=15)

    plt.savefig(outputDir+"/injection_scan_summary.png",format='png',bbox_inches='tight')
    
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
