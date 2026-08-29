import glob
import argparse
import pandas as pd
import ROOT
ROOT.TH2F.AddDirectory(False)
import os, sys
import uproot
import numpy as np
import matplotlib.pyplot as plt
import yaml

def fit_master(inl):
    x0 = np.arange(len(inl))
    y0 = inl
    c0 = int(len(x0) * 0.10)
    return np.polyfit(x0[c0:-c0], inl[c0:-c0], 1)

class tdc_raw_analyzer():
    def __init__(self, odir = './', tdc_name = 'toa', fr_channels_per_run = 4, calib = 'master'):
        self.odir = odir
        self.calib = calib
        self.tdc_name = tdc_name

        self._tunpacked = 'unpacker_data/hgcroc'
        self._tsummary = 'runsummary/summary'
        self._fr_channels_per_run = fr_channels_per_run
        self._channels_per_run = int(72/self._fr_channels_per_run)
            
        self.master_pars = {'CTRL_IN_REF_CTDC_P_D': 1,   # up 
                            'CTRL_IN_SIG_CTDC_P_D': -1}  # down

        self.individual_pars = {f'DAC_CAL_CTDC_{self.tdc_name.upper()}': 1}
 
        self.fnames = glob.glob(odir + '/acg*.root')
        self.fidx_pvals = self.get_scan_vals()
        self.fidx_ch_chunks = self.get_ch_chunks()
        self.nchips = self.get_nchips()


    def get_ch_chunks(self):
        # return {file_index : ch_chunk} with ch_chunk (0,..., self._fr_channels_per_run) corresponds to each file
        # note: one could also get the probed channels from metadata instead
        fidx_ch_chunks = {}
        val = 0
        for fidx, fname in enumerate(self.fnames): 
            if self.calib == 'master': 
                fidx_ch_chunks[fidx] = 0
            elif self.calib == 'individual':
                fidx_ch_chunks[fidx] = fidx % self._fr_channels_per_run
        return fidx_ch_chunks
                
    def get_nchips(self):
        with uproot.open(self.fnames[0]) as fin:
            tree = fin[self._tsummary]
            df = tree.arrays(['chip', 'channel'], library='pd')
            nchips = len(df.groupby(['chip']).nunique())
        del df
        return nchips
    
    def get_scan_vals(self):        
        # return dict {file_index : parameter_value}; the value of the master down parameter is set to a negative value
        fidx_vals = {}
        val = 0

        for fidx, fname in enumerate(self.fnames): 
            with uproot.open(fname) as fin:
                tree = fin[self._tsummary]

                if any([pname.encode() in tree.keys() for pname in list(self.master_pars.keys())]):
                    for pname, psign in self.master_pars.items():
                        if pname.encode() in tree.keys():
                            val = psign *  tree.arrays([pname], library='pd').iloc[0][pname]

                elif any([pname.encode() in tree.keys() for pname in list(self.individual_pars.keys())]):
                    for pname, _ in self.individual_pars.items():
                        if pname.encode() in tree.keys():
                            val = tree.arrays([pname], library='pd').iloc[0][pname]
                else: 
                    print("no master or individual tdc calibration parameter in tree")
                    sys.exit(0)                        

            del tree
            
            fidx_vals[fidx] = val
        return fidx_vals

    def avg_inl_slope_scan(self):        
        avg_slopes = []
        for fidx, fname in enumerate(self.fnames): 
            avg_slope = self.avg_inl_slope(fidx)
            avg_slope['pval'] = self.fidx_pvals[fidx]
            avg_slopes.append(avg_slope)
        return avg_slopes

    def get_inl(self, fidx = 0, ch_chunk = 0):
        # returns a list (with length = nchips) of TH2F with x = roc_ichannel, y = coarse TDC, z = INL

        fname = self.fnames[fidx]
        print(fname)    

        df = ROOT.RDataFrame(self._tunpacked, fname)            
        
        # roc_channel: translate channel number id per half into id per roc
        # roc_ichannel: probed channels idxs
        # c_{tdc_name}: coarse (5 bits) tdc folding 
 
        df = df.Filter('channel < 36') \
               .Define('roc_channel', 'channel + half*(39 - 3)') \
               .Filter(f'roc_channel % {self._fr_channels_per_run} == 0 + {ch_chunk}') \
               .Define('roc_ichannel', f'roc_channel / {self._fr_channels_per_run}') \
               .Define(f'c_{self.tdc_name}', f'floor(({self.tdc_name} % int(pow(2,8)))/int(pow(2,3)))') 

        hinls = []

        for chip in range(self.nchips):

            hinl = ROOT.TH2F(f'tdc_inl_{chip}', f';channel;{self.tdc_name} (ctdc) ;INL', 
                             int(72/self._fr_channels_per_run), 0 , 72/self._fr_channels_per_run, 32, 0, 32)

            htdc = df.Filter(f'chip == {chip}') \
                     .Histo2D(('tdc', f';channel;{self.tdc_name} (ctdc);Events', 
                               int(72/self._fr_channels_per_run), 0 , 72/self._fr_channels_per_run, 32, 0, 32),
                              'roc_ichannel', f'c_{self.tdc_name}')

            n_tot = htdc.ProjectionX('tot',0, htdc.GetNbinsY()+1)

            
            for j in range(1, htdc.GetNbinsY()+1):

                r = htdc.ProjectionX(f'b{j}', 0, j)

                for i in range(1, htdc.GetNbinsX()+1):
                    #https://gitlab.cern.ch/fcouderc/hgtdc/-/blob/master/tdc_calibration/tdc_codes.py#L91
                    hinl.SetBinContent(i, j, (r.GetBinContent(i)/n_tot.GetBinContent(i)) * htdc.GetNbinsY() - j)

            hinls.append(hinl)

        return hinls

    def avg_inl_slope(self, fidx = 0):
        # returns a dict {roc : [avg_slope_half0, avg_slope_half1]}

        avg_slope = {}
        avg_intercept = {}
        
        hinls = self.get_inl(fidx)

        for chip in range(self.nchips):

            hinl = hinls[chip]

            inl_slope = [] 
            inl_intercept = [] 

            fig, ax = plt.subplots()
            ctdc = np.arange(32)
            for i in range(1, hinl.GetNbinsX()+1):
                h_ch_inl = hinl.ProjectionY(f'p{i}', i, i+1)


                inl = h_ch_inl.GetArray()

                inl = np.ndarray((h_ch_inl.GetNbinsX()+2,), dtype=np.float64, buffer=inl, order='C') 
                inl = inl * int(pow(2,3)) # norm by unit of LSB in ps (coarse binning) 
                inl = inl[1:-1] # remove underflow/overflow
                ch = (i-1) * self._fr_channels_per_run
                fit_result = fit_master(inl)
                inl_slope.append(fit_result[0])
                inl_intercept.append(fit_result[1])

                plt.plot(ctdc, inl, '-o', label = ch,)

            halflen = int(72/(self._fr_channels_per_run * 2))

            avg_slope[chip] = [
                sum(inl_slope[0:halflen - 1])/len(inl_slope[0:halflen - 1]),             # half 0
                sum(inl_slope[halflen: -1])/len(inl_slope[halflen: -1])                  # half 1
            ]

            avg_intercept[chip] = [
                sum(inl_intercept[0:halflen - 1])/len(inl_intercept[0:halflen - 1]),             # half 0
                sum(inl_intercept[halflen: -1])/len(inl_intercept[halflen: -1])                  # half 1
            ]
            
            avg_line = (avg_intercept[chip][0] + avg_intercept[chip][1])/2 + (avg_slope[chip][0] + avg_slope[chip][1])*(ctdc/2)

            plt.plot(ctdc, avg_line, '--', label = 'avg', color = 'b')

            plt.legend(ncol=2)
            plt.savefig(f'{self.odir}/ctdc_inls_roc{chip}_pval{self.fidx_pvals[fidx]}.png')
            plt.close(fig)

        return avg_slope 

    def get_raw_chi2(self, hinl, ch_chunk = 0):        
        ch_raw_chi2 = {}
        
        for i in range(1, hinl.GetNbinsX()+1):
            h_ch_inl = hinl.ProjectionY(f'p{i}', i, i+1)
            
            inl = h_ch_inl.GetArray()
            
            inl = np.ndarray((h_ch_inl.GetNbinsX()+2,), dtype=np.float64, buffer=inl, order='C') 
            inl = inl * int(pow(2,3)) # norm by unit of LSB in ps (coarse binning) 
            inl = inl[1:-1] # remove underflow/overflow
            
            ch = (i-1) * self._fr_channels_per_run + ch_chunk
            
            ch_raw_chi2[ch] = inl.T @ inl

        return ch_raw_chi2
                        
                    
    def raw_chi2_scan(self):        
        chi2_ch_pval = []
        for fidx, fname in enumerate(self.fnames): 
            ch_chunk = self.fidx_ch_chunks[fidx]
            hinls = self.get_inl(fidx, ch_chunk)
            for chip in range(self.nchips):
                hinl = hinls[chip]
                chi2 = self.get_raw_chi2(hinl, ch_chunk)                
                chi2['pval'] = self.fidx_pvals[fidx]
                chi2['roc'] = chip

                chi2_ch_pval.append(chi2)

        return chi2_ch_pval



    def get_best_parameters(self):
        if self.calib == 'master': 
            return self.get_best_master_parameters()
        elif self.calib == 'individual':
            return self.get_best_individual_parameters()
        

    def get_best_master_parameters(self):
        avg_slopes = self.avg_inl_slope_scan()
        df = pd.DataFrame(avg_slopes).set_index('pval').sort_index()
        best_pars = {}
        for chip in df.columns:      
            best_pars.setdefault(chip, [])
            df_chip = pd.DataFrame(df[chip].tolist(), index= df.index)
            df_chip.columns = ['half0', 'half1']
            p_fits = []
            for half in df_chip.columns:
                p_fit = np.polyfit(df_chip[half].index.values, df_chip[half], 5)

                p_fits.append(np.poly1d(p_fit))
                try:
                    real_roots = [r.real for r in p_fits[-1].roots if (r.imag == 0 and abs(r.real) <= 31)]
                    best = int(np.round(real_roots[0])) if len(real_roots) >= 1 else np.nan
                except np.linalg.LinAlgError:
                    best = np.nan
                best_pars[chip].append(best)

                x = np.linspace(df_chip.index.min(), df_chip.index.max(), 100)
                
            plt.figure(figsize=[8, 5])

            for half in df_chip.columns:
                df_chip.plot(y = half, ls='', marker='.', ax=plt.gca(), use_index = True)
                colors = [li.get_color() for li in plt.gca().get_lines()]

            plt.axhline(0, ls='-', color='k')
            plt.axvline(0, ls='-', color='k')
            
            for i in [0, 1]: plt.plot(x, p_fits[i](x), color=colors[i], ls='--')
            
            plt.gca().set_ylabel('<INL slope>', ha='left')
            plt.gca().set_xlabel('ref/sig CTDC', ha='right', x=1)

            plt.savefig(f'{self.odir}/ctdc_slopes_roc{chip}.png')
            plt.close()

        return best_pars
        
    def get_best_individual_parameters(self):   # not implemented
        best_pars = {}
        chi2_ch_pval = self.raw_chi2_scan()       

        df = pd.DataFrame(chi2_ch_pval).groupby(['roc', 'pval']).max().reset_index() \
                                                                .set_index('pval').sort_index()
        
        for chip, df_chip in df.groupby('roc'): 

            best_pars.setdefault(chip, {})


            fig, axs = plt.subplots(2, 2, figsize=(15, 15))
            axs = axs.flatten()
            idx_ch = df_chip.std() > 25
            df_chip = df_chip.loc[:, idx_ch]
            min_chi2 = df_chip.idxmin()

            best_pars[chip] = {ch: int(min_chi2.loc[ch]) for ch in min_chi2.index}

            for ch_chunk in range(self._fr_channels_per_run):                                 
                print(df_chip)
                df_chip.iloc[:, self._channels_per_run*ch_chunk: self._channels_per_run*(ch_chunk+1)].plot(ax = axs[ch_chunk])
                plt.legend(ncol=2)

            plt.savefig(f'{self.odir}/ctdc_chi2_roc{chip}.png')      
            plt.close(fig)
            
        return best_pars

    def write_to_yaml(self, best_pars):
        pars = {'master': self.master_pars,
                'individual': self.individual_pars}[self.calib]
      
        
        yaml_dict={}

        rockeys = []
        with open("%s/initial_full_config.yaml"%(self.odir)) as fin:
            initconfig = yaml.safe_load(fin)
            for key in initconfig.keys():
                if key.find('roc')==0:
                    rockeys.append(key)

        rockeys.sort()

        for chip in range(self.nchips):
            if chip<len(rockeys):
                chip_key_name = rockeys[chip]
                
                if self.calib == 'master':
                    yaml_dict[chip_key_name] = {
                        'sc' : {
                            'MasterTdc' : {
                            }
                        }
                    }
                    
                    for half in [0,1]:                        
                        pars_dict = {}
                        for pname, psign in pars.items():
                            pars_dict[pname] = abs(best_pars[chip][half]) if best_pars[chip][half] * psign > -1 else 0
                        yaml_dict[chip_key_name]['sc']['MasterTdc'][half] = pars_dict

                elif self.calib == 'individual':
                    yaml_dict[chip_key_name] = {
                        'sc' : {
                           'ch' : {
                            }
                        }
                    }                    
                    for ch in range(0, 72):
                        pars_dict = {}
                        for pname, psign in pars.items():
                            pars_dict[pname] = best_pars[chip][ch] if ch in best_pars[chip].keys() else 0
                        yaml_dict[chip_key_name]['sc']['ch'][ch] = pars_dict
                        


        with open(self.odir+f'/{self.tdc_name}_{self.calib}.yaml','w') as fout:
            yaml.dump(yaml_dict,fout)
            


if __name__ == "__main__":

    if len(sys.argv) > 2:
        tdc_name = sys.argv[1]
        odir = sys.argv[2]
        calib = sys.argv[3] if len(sys.argv) == 4 else 'master'

        analyzer = tdc_raw_analyzer(odir=odir, tdc_name=tdc_name, calib=calib)
        
        best_pars = analyzer.get_best_parameters()

        analyzer.write_to_yaml(best_pars)
        
    else:
        print("No argument given")
    
            

            
            
