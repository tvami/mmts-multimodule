import os,glob,yaml,sys

import level0.aggregate_summary as agg
from summaryWriter import *


if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    
    parser.add_option("-i", "--inputDir", dest="inputDir",
                      help="input directory with the all DUT data")
    
    parser.add_option("-n", "--nDirs", dest="nDirs",default=11,type=int,
                      help="expected number of subdirectories per chip (i.e. the full test procedure went fine for a given chip)")
    
    (options, args) = parser.parse_args()
    print(options)
    
    good=[]
    bad=[]
    okish=[]

    chips = glob.glob("%s/*"%options.inputDir)
    for chipdir in chips:
        try:
            chip = chipdir.split("%s/"%options.inputDir)[1]
            if chip.isdigit()==False:
                continue
        except:
            print("wrong format for %s -> exit"%chipdir)
            sys.exit()
        
        dirs = [ name for name in os.listdir(chipdir) if os.path.isdir("%s/%s"%(chipdir,name)) ]
        
        if len(dirs)!=options.nDirs:
            bad.append(chip)
            continue

        try:
            with open("%s/summary.yaml"%chipdir) as fin:
                summary = yaml.safe_load(fin)
        except:
            print("summary.yaml not found in %s -> exit"%chipdir)
            sys.exit()
            
        ped_summary = summary["pedestal_run"]
        if len(ped_summary.keys())>1:
            print("check pedestal run summary files in %s"%chipdir)
        ped_summary = ped_summary[list(ped_summary.keys())[0]]
        # print(chip,ped_summary)
        bad_pedestal = ( ped_summary["stats"]["chip0"]["MeanPedestal"]>35 or 
                         ped_summary["stats"]["chip0"]["StdPedestal"]>10 or 
                         ped_summary["stats"]["chip0"]["MeanNoise"]>2 or 
                         ped_summary["bad_channels"]["chip0"]["total"]>=5 )

        ped_scan_summary = summary["pedestal_scan"]
        ped_scan_summary = ped_scan_summary[list(ped_scan_summary.keys())[0]]
        bad_pedestal_scan = ( len(list( set(ped_scan_summary['bad_channels_pedestal']['chip0']['ch'])    | set(ped_scan_summary['bad_channels_ref_dac']['chip0']['ch'] ) )) +
                              len(list( set(ped_scan_summary['bad_channels_pedestal']['chip0']['cm'])    | set(ped_scan_summary['bad_channels_ref_dac']['chip0']['cm'] ) )) +
                              len(list( set(ped_scan_summary['bad_channels_pedestal']['chip0']['calib']) | set(ped_scan_summary['bad_channels_ref_dac']['chip0']['calib'] ) )) > 5 )


        inj_scan_summary = summary["injection_scan"]
        if len(inj_scan_summary.keys())>1:
            print("check injetion scan summary files in %s"%chipdir)
        inj_scan_summary = inj_scan_summary[list(inj_scan_summary.keys())[0]]
        bad_inj_scan = inj_scan_summary['bad_channels_adc']['chip0']['total']>5
        # we used the intersection for the TDCs because we have seen weird toa behavior (not always reproducible) without tot issue
        okish_inj_scan = ( len( set.intersection(set(inj_scan_summary['bad_channels_toa']['chip0']['ch'])    , set(inj_scan_summary['bad_channels_tot']['chip0']['ch']) )) +
                           len( set.intersection(set(inj_scan_summary['bad_channels_toa']['chip0']['cm'])    , set(inj_scan_summary['bad_channels_tot']['chip0']['cm']) )) +
                           len( set.intersection(set(inj_scan_summary['bad_channels_toa']['chip0']['calib']) , set(inj_scan_summary['bad_channels_tot']['chip0']['calib']) )) > 5 )


        if bad_pedestal:
            bad.append(chip)
        elif bad_pedestal_scan:
            bad.append(chip)
        elif bad_inj_scan:
            bad.append(chip)
        elif okish_inj_scan:
            okish.append(chip)
        else:
            good.append(chip)
        

    print("bad chips : ",bad)
    print("good chips : ",good)
    print("okish chips : ",okish)

    print( "ngood = %d ; nokish = %d ; nbad = %d"%(len(good), len(okish), len(bad)) )
    
