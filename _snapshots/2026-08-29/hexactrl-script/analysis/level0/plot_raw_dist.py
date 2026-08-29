import os,subprocess, threading, re, errno
import uproot
import matplotlib
#matplotlib.use('tkagg')
import matplotlib.pyplot as plt
import level0.analyzer as an


if __name__ == "__main__":

    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option("-f", "--inputfile", dest="inputfile",
                      help="raw data input file")

    parser.add_option("-o", "--odir", dest="odir",
                      help="output plot directory (will go to same dir as input file if not set)")

    (options, args) = parser.parse_args()
    print(options)

    if options.odir==None:
        odir = "%s/pedestal_dist/"%( os.path.dirname(options.inputfile) )
    else:
        odir = options.odir
    try:
        os.makedirs(odir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise   
        pass
        
    if options.inputfile.endswith('.root'):
        reader = an.rawroot_reader( fin=options.inputfile )
        data = reader.df
    elif options.inputfile.endswith('.raw'):
        raw_analyzer = an.raw_analyzer(odir=odir)
        raw_analyzer.add(fin=options.inputfile)
        raw_analyzer.mergeData()
        data = raw_analyzer.data
    else: 
        print( "ERROR input file format should .root or .raw -> exit")
        exit
    print(data)

    #nchip = len( data.groupby('chip').nunique() )
    fig, ax = plt.subplots(figsize=(15,9))
    for chip in data.groupby('chip')['chip'].mean():
        chip_data = data[ (data['chip']==chip) ]
        nhalf = len( chip_data.groupby('half').nunique() ) #2 in principle
        for half in range(nhalf):
            half_data = chip_data[ (chip_data['half']==half) ]
            nchannels = len( half_data.groupby('channel').nunique() ) #39 in principle
            print('chip %d,half %d'%(chip,half))
            for chan in range(nchannels): 
                chan_data = half_data[ half_data['channel']==chan ] 
                nbins=int(chan_data['adc'].max()-chan_data['adc'].min())
                if nbins>0: pass
                else : nbins=10
                ax.hist(  chan_data['adc'], bins=nbins, color='blue',alpha=0.9)
            
                for tick in ax.xaxis.get_major_ticks():
                    tick.label.set_fontsize(15) 
                for tick in ax.yaxis.get_major_ticks():
                    tick.label.set_fontsize(15) 

                if chan<36:
                    plt.title('Channel %d'%(chan),size=18)
                elif chan==36:
                    plt.title('Calib channel',size=18)
                else:
                    plt.title('Common mode channel %d'%(chan-37),size=18)

                plt.xlabel(r'Signal [ADC counts]',fontsize=18)
                plt.ylabel(r'# events',fontsize=18)

                
                plt.savefig("%s/adc_chip%d_half%d_channel%s.png"%(odir,chip,half,str(chan).zfill(2)))
                plt.cla()
    
