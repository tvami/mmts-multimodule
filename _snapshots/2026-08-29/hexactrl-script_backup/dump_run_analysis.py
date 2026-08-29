import glob, yaml
import numpy as np
import matplotlib.pyplot as plt
from analysis.level0.analyzer import *
import matplotlib as mpl
import matplotlib.ticker as ticker
from matplotlib.offsetbox import AnchoredText

# event in run
def event_to_time(event, L1Offset):
    if event <= L1Offset: 
        time = (L1Offset - event) * 0.025 + event * 43 * 0.025
    else:
        time = (L1Offset - event + 512) * 0.025 + event * 43 * 0.025
    return time

# Currently works only with single chip

class dump_run_analyzer(analyzer):
    def __init__(self, odir = "./", treename = 'unpacker_data/hgcroc', branches = None):
        analyzer.__init__(self, odir = odir, treename = treename, branches = branches)

        conf_file = self.odir+'/initial_full_config.yaml'
        with open(conf_file) as fin: 
            self.initConfig = yaml.safe_load(fin)

        self.L1Offset = self.initConfig['roc_s0']['sc']['DigitalHalf']['all']['L1Offset']
        self.events_per_readout = self.initConfig['daq']['Number_of_events_per_readout']
        # default ref_adc value in case ADC is not set
        self.ref_adc = 0
        # read ref_adc from yaml file if it exists
        if 'ExtData' in self.initConfig['roc_s0']['sc']['ch']['all']:
            self.ref_adc = self.initConfig['roc_s0']['sc']['ch']['all']['ExtData']

    def add_bit_error_count(self):
        ref_adc = self.ref_adc
        # only perform this if ADC is set
        if ref_adc:
            L1Offset = self.L1Offset
            events_per_readout = int(self.events_per_readout)
            data = self.data.copy()
            
            data["ped_diff"] = data["adc"] ^ ref_adc
            data["bitflips"] = data["ped_diff"].apply(lambda x: bin(x).count("1"))
            data["one_to_zero_diff"] = data["ped_diff"] & ref_adc
            data["one_to_zero_flips"] = data["one_to_zero_diff"].apply(lambda x: bin(x).count("1"))

            self.data = data
            print("Bit error counts added to data.")
        else:
            print("ADC not set.")

    def makePlots(self):
        odir = self.odir
        ref_adc = int(self.ref_adc)
        L1Offset = int(self.L1Offset)
        events_per_readout = int(self.events_per_readout)
        data = self.data.copy()

        data = data.reset_index()

        nchannel = len(data["channel"].unique()) * 2 # for the 2 halfs

        data["run"] = data.index.to_series() // (events_per_readout * nchannel)
        data["event_in_run"] = np.array(data.event) % events_per_readout
        '''
        fig = plt.subplots(figsize=(12,10))
        plt.plot(df.event, df.wadd, '.')
        plt.xlabel('event')
        plt.ylabel('wadd')
        plt.savefig(odir+'/wadd_vs_event.png')
        plt.clf()

        plt.plot(df.wadd, df.bxcounter, '.')
        plt.xlabel('wadd')
        plt.ylabel('bxcounter')
        plt.savefig(odir+'/bxcounter_vs_wadd.png')
        plt.clf()

        plt.plot(df.event, df.bxcounter, '.')
        plt.xlabel('event')
        plt.ylabel('bxcounter')
        plt.savefig(odir+"/bxcounter_vs_event.png")
        plt.clf()
        '''
        if ref_adc:
            hfig, hax = plt.subplots(figsize = (16, 9))
            hbottom = 0
            for run in data.run.unique():
                sel = data["run"] == run
                data_sel = data.loc[sel, ["run", "event_in_run", "bitflips", "one_to_zero_flips"]].copy()
                #print(data_sel)
                groupped = data_sel.groupby("event_in_run").sum() # to sum all bitflips in event 
                times = groupped.index.to_series().apply(event_to_time, args = (L1Offset,)).to_numpy()
                total_bitflips = groupped["bitflips"].astype(float).to_numpy()
                one_to_zero_flips = groupped["one_to_zero_flips"].to_numpy()
                
                fig, ax = plt.subplots(figsize = (16, 9))
                
                ax.plot(times, total_bitflips, marker = ".", linestyle = "none", 
                        color = "tab:blue", alpha = 0.7, label = 'total bitflips')
                ax.plot(times, one_to_zero_flips, marker = ".", linestyle = "none", 
                        fillstyle = "none", markeredgecolor = "black", alpha = 0.7, label = '1 -> 0 bitflips')
                ax.legend(loc = 'upper left')
                
                ax.set_xlabel('Time in memory (us)')
                ax.set_ylabel('ADC bit error count')
                ax.grid(which='major', alpha=0.7)
                ax.grid(which='minor',linestyle='--', alpha=0.4)
                
                ax.yaxis.set_major_locator(ticker.AutoLocator())
                ax.yaxis.set_minor_locator(ticker.AutoLocator())
                ax.xaxis.set_major_locator(ticker.MultipleLocator(100))
                ax.xaxis.set_minor_locator(ticker.MultipleLocator(10))
                
                txt = 'L1Offset: %d' % (L1Offset)
                anchored_text = AnchoredText(txt, loc = 'center left', prop = {'fontsize': 20})
                ax.add_artist(anchored_text)             
                #plt.yscale("log")
                ax.set_title("ADC bit error count in all channels per event for run %d" % (run))
                fig.savefig(odir + "/run%d_bit_error_count.png" % (run))
                plt.close(fig)

                # add to combined bar plot
                hax.bar(times, total_bitflips, label = run, bottom = hbottom, alpha = 1, width = 0.5)
                hbottom += total_bitflips
            # format bar plot
            hax.legend(loc = 'upper left', ncol = 3, title = "Run #", fontsize = 10)
            hax.set_xlim((0, 300))
            hax.set_ylim((0, 50))
            hax.set_xlabel('Time in memory (us)')
            hax.set_ylabel('ADC bit error count')
            hax.grid(which='major', alpha=0.7)
            hax.grid(which='minor', linestyle='--', alpha = 0.4)
            hax.set_title("ADC bit error count in all runs")
            hfig.savefig(odir + "/all_runs_bit_error_barplot.png")


if __name__ == '__main__':
    ref_adc = 682
    odir = 'data/'
    if len(sys.argv) > 1:
        odir = sys.argv[1]
    indir = odir
    dump_analyzer = dump_run_analyzer(odir=odir, treename = 'unpacker_data/hgcroc')
    files = glob.glob(indir+"/dump_run*.root")
    for f in files:
        dump_analyzer.add(f)
    dump_analyzer.mergeData()
    dump_analyzer.makePlots()


