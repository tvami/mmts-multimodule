import glob
import numpy as np
import matplotlib.pyplot as plt
from level0.analyzer import *


def corr(x, y=None):
    mean_x, std_x = np.mean(x), np.std(x)
    if y is None:
        y, mean_y, std_y = x, mean_x, std_x
    else:
        mean_y, std_y = np.mean(y), np.std(y)
    ret = np.correlate(x - mean_x, y - mean_y, mode='full') / len(x) / (std_x * std_y)
    return ret[int(ret.size / 2):]


class autocorrelation_run_analyzer(analyzer):
    def __init__(self, odir="./", treename='unpacker_data/hgcroc', branches=None):
        analyzer.__init__(self, odir=odir, treename=treename, branches=branches)

    def makePlots(self):
        data = self.data.copy()
        for chip in sorted(data.chip.unique()):
            df = data.query('chip==%d' % chip)

            # raw data plot
            fig, axs = plt.subplots(1, 2, figsize=(12, 7))
            for ch in sorted(df.channel.unique()):
                df_sel = df.query('half==0 & channel==%d' % ch)
                ax = axs[0]
                ax.plot(df_sel.event, df_sel.adc, '.-')
                ax.set_xlabel("Event")
                ax.set_ylabel("ADC")
                ax.set_title('Half 0')

                df_sel = df.query('half==1 & channel==%d' % ch)
                ax = axs[1]
                ax.plot(df_sel.event, df_sel.adc, '.-')
                ax.set_xlabel("Event")
                ax.set_title('Half 1')
            fig.suptitle("Raw data (chip %d)" % chip, fontsize=25)
            fig.tight_layout()
            fig.savefig(self.odir + "/rawdata_chip%d.png" % chip)

            # autocorrelation
            fig, axs = plt.subplots(2, 1, figsize=(12, 10))
            corr_0 = []
            corr_1 = []
            for ch in sorted(df.channel.unique()):
                df_sel = df.query('half==0 & channel==%d' % ch)
                if df_sel.adc.max() > 700:  # FIXME: check this cut
                    continue
                ax = axs[0]
                x = corr(df_sel.adc.values)
                ax.plot(x[:20], '.-')
                corr_0.append(list(x))

                df_sel = df.query('half==1 & channel==%d' % ch)
                if df_sel.adc.max() > 700:  # FIXME: check this cut
                    continue
                ax = axs[1]
                x = corr(df_sel.adc.values)
                ax.plot(x[:20], '.-')
                corr_1.append(x)

            corr_0 = np.stack(corr_0, axis=1)
            average = np.mean(corr_0, axis=1)
            axs[0].plot(average[:20], '--', color="k", linewidth=4.0)
            axs[0].set_ylabel("Autocorrelation")
            axs[0].set_title("Half 0")

            corr_1 = np.stack(corr_1, axis=1)
            average = np.mean(corr_1, axis=1)
            axs[1].plot(average[:20], '--', color="k", linewidth=4.0)
            axs[1].set_xlabel("Index")
            axs[1].set_ylabel("Autocorrelation")
            axs[1].set_title("Half 1")

            for ax in axs:
                ax.grid()
            fig.suptitle("Autocorrelation (chip %d)" % chip, fontsize=25)
            fig.tight_layout()
            fig.savefig(self.odir + "/autocorrelation_chip%d.png" % chip)


if __name__ == '__main__':
    odir = 'data/'
    if len(sys.argv) > 1:
        odir = sys.argv[1]
    indir = odir
    autocorr_analyzer = autocorrelation_run_analyzer(odir=odir, treename='unpacker_data/hgcroc')
    files = glob.glob(indir + "/*.root")
    for f in files:
        autocorr_analyzer.add(f)
    autocorr_analyzer.mergeData()
    autocorr_analyzer.makePlots()
