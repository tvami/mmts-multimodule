import uproot
import pandas as pd
import numpy as np
import os,re,datetime
import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 114
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import subprocess, sys
import yaml

from nested_dict import nested_dict

plt.rcParams.update({'font.size': 22})

class reader:
    def __init__(self, filename, treename='runsummary/summary', branches=None):
        print("Reading file %s (tree %s)" % (filename, treename))
        tree = uproot.open(filename)[treename]
        self.df = tree.arrays(branches, library='pd')

class analyzer:
    def __init__(self, odir="./", treename='runsummary/summary', branches=None):
        self.odir=odir
        if not os.path.exists(odir):
            os.makedirs(odir)
        self._treename = treename
        self._branches = branches
        self.dataFrames = []
        self._summary = nested_dict()
        self.fname=""

    def __del__(self):
        os.system("rm %s"%(self.fname))

    def add(self, fname):
        pass
        # r = reader(fname, treename=self._treename, branches=self._branches)
        # self.dataFrames.append(r.df)

    def mergeData(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.fname="/dev/shm/tmp%s.root"%timestamp
        os.system("hadd -f %s %s/*.root"%(self.fname,self.odir))
        self.data = reader(self.fname, treename=self._treename, branches=self._branches).df
        if 'half' not in self.data.keys() and "channel" in self.data.keys():
            self.data['half'] = self.data.eval(
                '((channeltype==0) & (channel>=36)) | ((channeltype==1) & (channel>0)) | ((channeltype==100) & (channel>=2))').astype('int')

    def altMergeData(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.fname="/dev/shm/tmp%s.root"%timestamp
        os.system("hadd -f %s %s/*/*.root"%(self.fname,self.odir))
        self.data = reader(self.fname, treename=self._treename, branches=self._branches).df

    def makePlots(self):
        pass

    def fit(self,sel):
        pass

    def addSummary(self):
        pass

    def writeSummary(self):
        with open(self.odir + '/analysis_summary.yaml', 'w') as fout:
            yaml.dump(self._summary.to_dict(), fout)

class rawroot_reader:
    def __init__(self,fin):
        print("reading %s"%(fin))
        afile = uproot.open(fin)
        tree = afile['unpacker_data']['hgcroc']
        self.df = tree.arrays( ['*'], library='pd' )

class raw_analyzer(analyzer):

    def __run_unpacker__(self,fin):
        fout  = '%s/raw_%s.root'%(self.odir,os.path.basename( re.split('.raw',fin)[0] ))
        flog  = '%s/raw_%s.log'%( self.odir,os.path.basename( re.split('.raw',fin)[0] ))
        cmd='unpack -i ' + fin + ' -o ' + fout
        with open(flog,'w') as logout:
            subprocess.check_output( cmd, shell=True,stderr=logout  )
        return fout


    def add(self,fin):
        fout = self.__run_unpacker__(fin)
        r = rawroot_reader(fin=fout)
        self.dataFrames.append(r.df)
