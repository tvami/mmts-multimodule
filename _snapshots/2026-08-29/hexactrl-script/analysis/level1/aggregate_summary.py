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
    
    chips = glob.glob("%s/*"%options.inputDir)
    for chipdir in chips:
        try:
            chip = chipdir.split("%s/"%options.inputDir)[1]
            if chip.isdigit()==False:
                continue
        except:
            print("wrong format for %s -> exit")
            sys.exit()
        
        dirs = [ name for name in os.listdir(chipdir) if os.path.isdir("%s/%s"%(chipdir,name)) ]
        
        if len(dirs)!=options.nDirs:
            continue

        agg.aggregate(chipdir)
            
        
