import os,glob,yaml
import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 114
import matplotlib.pyplot as plt
import matplotlib.cm as cm

import level0.pedestal_run_analysis as analyzer
from summaryWriter import *

def run(inputDir,outputDir,reset):
    chips = glob.glob(inputDir+"/*")
    pedestal_mean=[]
    pedestal_rms=[]
    noise_mean=[]
    noise_rms=[]
    nbad_channels=[]
    for chip in chips:
        if chip.split(inputDir+"/")[1].isdigit()==False:
            continue
    
        pedruns = glob.glob(chip+"/pedestal_run/*")
        if len(pedruns)!=2 : 
            print("WRONG chip : %s"%chip)
            continue
        pedrun = sorted(pedruns)[1]

        if reset==True or os.path.isfile(pedrun+"/analysis_summary.yaml")==False:
            ped_analyzer = analyzer.pedestal_run_analyzer(odir=pedrun)
            writeSummary(odir=pedrun,analyzer=ped_analyzer)

        with open("%s/analysis_summary.yaml"%pedrun) as fin:
            summary = yaml.safe_load(fin)
            stats = summary["stats"]
            bad_channels = summary["bad_channels"]
            pedestal_mean.append(stats["chip0"]["MeanPedestal"])
            pedestal_rms.append(stats["chip0"]["StdPedestal"])
            noise_mean.append(stats["chip0"]["MeanNoise"])
            noise_rms.append(stats["chip0"]["StdNoise"])
            nbad_channels.append( len(bad_channels["chip0"]["ch"])+
                                  len(bad_channels["chip0"]["calib"])+
                                  len(bad_channels["chip0"]["cm"]) )

    # print(pedestal_mean)
    # print(pedestal_rms)
    # print(noise_mean)
    # print(noise_rms)

    fig, axes = plt.subplots(2,3,figsize=(24,16))
    axes[0,0].hist( pedestal_mean,bins=25 )
    axes[0,0].set_xlabel(r'Chip average pedestal [ADC counts]')
    
    axes[0,1].hist( pedestal_rms,bins=25 )
    axes[0,1].set_xlabel(r'Chip pedestal std [ADC counts]')

    axes[1,0].hist( noise_mean,bins=25 )
    axes[1,0].set_xlabel(r'Chip average noise [ADC counts]')
    
    axes[1,1].hist( noise_rms,bins=25 )
    axes[1,1].set_xlabel(r'Chip noise standard dev [ADC counts]')

    axes[0,2].hist( nbad_channels )
    axes[0,2].set_xlabel(r'Number of bad channels (0 noise channels)')
    
    plt.savefig(outputDir+"/pedestal_run_summary.png",format='png',bbox_inches='tight')
    
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
