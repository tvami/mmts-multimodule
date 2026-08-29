import yaml
import numpy as np
import os,re
import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 114
import matplotlib.pyplot as plt
import matplotlib.cm as cm


def plot(inputf,chip):
    with open(inputf) as fin:
        data = yaml.safe_load(fin)

    cmap = cm.get_cmap('Dark2')
    halfColor=0
    fig, ax = plt.subplots(1,1,figsize=(16,9))
    for half in data['half'].keys():
        inctestdata=[]
        print(half)
        calibDacs = list(data['half'][half]['Calib_dac'].keys())
        for caldac in calibDacs:
            inctestdata.append(data['half'][half]['Calib_dac'][caldac]['roc_s0'])

        plt.plot( calibDacs, inctestdata,
                  color=cmap(half), label=r'Half %d'%(half),marker='o')
        
    plt.xlabel(r'Injection [DAC]')
    plt.ylabel(r'Signal [V]')

    h,l=ax.get_legend_handles_labels()
    ax.legend(handles=h,labels=l,loc='upper right')
    plt.show()
    
if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    
    parser.add_option("-i", "--input", dest="input",
                      help="input yaml file")

    parser.add_option("-c", "--chip", dest="chip",
                      help="chip ID")


    (options, args) = parser.parse_args()
    print(options)
    

    plot(options.input,options.chip)
