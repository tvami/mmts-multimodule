import os,glob,yaml
import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 114
import matplotlib.pyplot as plt
import matplotlib.cm as cm

import level0.phase_scan_analysis as analyzer
from summaryWriter import *

def run(inputDir,outputDir,reset):
    chips = glob.glob(inputDir+"/*")
    
    mean_delta_ped=[]
    mean_delta_noise=[]
    for chip in chips:
        if chip.split(inputDir+"/")[1].isdigit()==False:
            continue
        run = glob.glob(chip+"/phase_scan/*")
        if len(run)!=1 : 
            print("WRONG chip : %s"%chip)
            continue
        # print(run[0])
        run = sorted(run)[0]
        yamlsummary = glob.glob(chip+"/phase_scan/*/analysis_summary.yaml")
        # print(yamlsummary)
        if (len(yamlsummary)==0 or reset==True):
            ## better with relative path?
            scan_analyzer = analyzer.phase_scan_analyzer(odir=run)
            writeSummary(odir=run,analyzer=scan_analyzer)

        with open("%s/analysis_summary.yaml"%run) as fin:
            summary = yaml.safe_load(fin)
            summary = summary["adc_vs_phase"]
            mean_delta_ped.append(summary["chip0"]["mean_delta_ped"])
            mean_delta_noise.append(summary["chip0"]["mean_delta_noise"])
        
    fig, axes = plt.subplots(1,2,figsize=(16,9))
    axes[0].hist( mean_delta_ped,bins=25 )
    axes[0].set_xlabel(r'Average pedestal variation with phase[ADC counts]')
    
    axes[1].hist( mean_delta_noise,bins=25 )
    axes[1].set_xlabel(r'Average noise variation with phase[ADC counts]')

    plt.savefig(outputDir+"/phase_scan_summary.png",format='png',bbox_inches='tight')

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
