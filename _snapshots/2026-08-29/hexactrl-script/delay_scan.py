import zmq_controler as zmqctrl
import os, sys, errno, datetime, json,glob, uproot3, pandas, numpy

# The analysis modules import each other as `from level0.analyzer import *`
# (top-level `level0`), so `analysis/` must be on sys.path. The hexactrl env
# normally sets this on PYTHONPATH; add it here so the script is self-contained.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analysis'))
import level0.delay_scan_analysis as analyzer
import matplotlib.pyplot as plt
import util

from time import sleep
class reader:
    def __init__(self,fname):
        afile = uproot3.open(fname)
        tree = afile['delayScanTree']
        self.df = tree.pandas.df( ['link','idelay','alignedCount','errorCount'] )

# Example: 
# python3 delay_scan.py -d hb -i hexactrl564610
#

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option("-d", "--dut", dest="dut",
                      help="device under test")

    parser.add_option("-i", "--hexaIP",
                      action="store", dest="hexaIP",
                      help="IP address of the zynq on the hexactrl board")

    parser.add_option("-f", "--configFile",default="./configs/init.yaml",
                      action="store", dest="configFile",
                      help="initial configuration yaml file")

    parser.add_option("-o", "--odir",
                      action="store", dest="odir",default='./data',
                      help="output base directory")

    parser.add_option("--i2cPort",
                      action="store", dest="i2cPort",default='5555',
                      help="output base directory")

    parser.add_option("--daqPort",
                      action="store", dest="daqPort",default='6000',
                      help="zmq socket port used by the fast control server (on the zynq)")

    parser.add_option("--pullerPort",
                      action="store", dest="pullerPort",default='6001',
                      help="zmq socket port used by the client executable (on the remote PC)")

    parser.add_option("-I", "--initialize",default=False,
                      action="store_true", dest="initialize",
                      help="set to re-initialize the ROCs and daq-server instead of only configuring")

    (options, args) = parser.parse_args()
    print(options)

    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)

    if options.initialize==True:
        print("Initializing the i2c sockets...")
        i2csocket.initialize()
        print("Initializing the daq sockets...")
        daqsocket.initialize()
        print("Initializing the client sockets...")
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        print("Client serverIP: %s"%(clisocket.yamlConfig['client']['serverIP']))
        clisocket.initialize()
    else:
        print("Configuring the i2c and daq sockets...")
        i2csocket.configure()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(timestamp)
    odir = "%s/%s/delay_scan/%s"%(os.path.realpath(options.odir),options.dut,timestamp)
    try:
        os.makedirs(odir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise   
        pass

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = 'delayScan'
    clisocket.configure()

    daqsocket.yamlConfig['daq']['active_menu']='delayScan'
    daqsocket.configure()
    print("Delay scan started, output directory: %s" % odir)

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    # util.acquire(daqsocket,clisocket)
    clisocket.start()
    daqsocket.start()
    while True:
        if daqsocket.is_done() == True:
            break
        else:
            sleep(0.01)
    # daq.stop()
    sleep(1)
    clisocket.stop()

    print("Delay scan results saved to: %s" % odir)
    delay_analyzer = analyzer.delay_scan_analyzer(odir=odir)
    files = glob.glob(odir+"/*.root")
    delay_analyzer.mergeData()
    delay_analyzer.makePlots()

    # a = reader( "%s/delayScan0.root"%(odir) )

    # links = []
    # nqualSummary = {} 
    # for link in daqsocket.yamlConfig['daq']['elinks_daq']:
    #     print(link)
    #     links.append( b'link_capture_daq.'+link['name'].encode("utf-8") )
    # for link in daqsocket.yamlConfig['daq']['elinks_trg']:
    #     links.append( b'link_capture_trg.'+link['name'].encode("utf-8") )
    
    # for link in links :
    #     print(link)
    #     data = a.df[ a.df['link']==link ]

    #     imax = 0
    #     wrun = 0

    #     nqual = dict(ngood=0, nbad=0, nturnon=0, wmax=0)
    #     for k, r in data.iterrows():
    #         if r['errorCount']<=1 and r['alignedCount']==128:
    #             wrun+=1
    #             nqual['ngood']+=1
    #         else:
    #             if wrun>nqual['wmax']:
    #                 nqual['wmax'] = wrun
    #                 imax = r['idelay']
    #             wrun = 0
    #             if r['errorCount']==255 and r['alignedCount']==0: 
    #                 nqual['nbad']+=1
    #             else: 
    #                 nqual['nturnon']+=1
        
    #     fig= plt.figure(figsize=(9,6))
    #     ax=fig.add_subplot(1,1,1)
        
    #     plt.xlim(0,512)
    #     plt.ylim(0,270)
    #     plt.scatter(data['idelay'], data['errorCount'], color='black', s=15, label=r'Number of errors')
    #     plt.scatter(data['idelay'], data['alignedCount'], color='red', s=15, label=r'Number of success')

    #     for tick in ax.xaxis.get_major_ticks():
    #         tick.label.set_fontsize(15) 
    #     for tick in ax.yaxis.get_major_ticks():
    #         tick.label.set_fontsize(15) 

    #     plt.xlabel(r'iDelay ',fontsize=15)
    #     plt.ylabel(r'#',fontsize=15)

    #     h,l=ax.get_legend_handles_labels() # get labels and handles from ax1
    #     wmax = nqual['wmax']
    #     arrcenter = imax-wmax/2
    #     ax.arrow(x=arrcenter, y=50, dx= wmax/2, dy=0, width=2, length_includes_head=True, color="green");
    #     ax.arrow(x=arrcenter, y=50, dx=-wmax/2, dy=0, width=2, length_includes_head=True, color="green");
    #     ax.text(x=arrcenter-30, y=55, s="w = %d"%(wmax), fontsize=15)
    #     ax.text(x=435, y=280, font='monospace', 
    #             s="%-7s = %3d\n%-7s = %3d \n%-7s = %3d" % ('nGood', nqual['ngood'], 'nBad', nqual['nbad'], 'nTurnon', nqual['nturnon']))
    #     ax.legend(handles=h,labels=l,loc='upper left',fontsize=15)

    #     title = str(link).split("b'")[1].split("'")[0]
    #     plt.title(title)
    #     title = str(link).split("b'")[1].split("'")[0]
    #     plt.savefig("%s/%s.png"%(odir,title))
    #     plt.close()
    #     nqualSummary[title] = nqual

    # with open("%s/summary.json"%(odir), 'w') as jfile:
    #     json.dump(nqualSummary, jfile)
    

    # let's configure back the client with default data port
    # clisocket.yamlConfig['global']['run_type'] = 'pedestal_run'
    # clisocket.yamlConfig['global']['data_push_port'] = '8888'
    # clisocket.configure()
