import argparse
import os
import matplotlib
matplotlib.use('tkagg')
import matplotlib.pyplot as plt
import level0.analyzer as an
import numpy as np
from pprint import pprint
from scipy.optimize import curve_fit
import pylandau
import pandas


def gaussian(x, a, x0, sigma):
    return a*np.exp(-(x-x0)**2/(2*sigma**2))

def pad2ElecID(pad):
    padmap = pandas.read_csv("../../hexmap/channel_maps/ld_pad_to_channel_mapping.csv")
    padmap = padmap[ padmap['PAD']==pad ]
    chip,half,channel = (0,0,0)
    chip=padmap['ASIC'].max()
    rocchannel = padmap['Channel'].max()
    channeltype = padmap['Channeltype'].max()
    if padmap['Channeltype'].max()==0:
        if padmap['Channel'].max()>=36:
            half = 1
            channel = padmap['Channel'].max()-36
        else:
            half = 0
            channel = padmap['Channel'].max()
    elif padmap['Channeltype'].max()==1:
        half = padmap['Channel'].max()
        channel = 36
    return chip,half,channel,rocchannel,channeltype

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-i','--infile',   help='input file',                  required=True)
    parser.add_argument('-p','--pad',      help='padID',                       type=int, required=True)
    parser.add_argument('-m','--adc_min',  help='min adc value for MIP peak',  type=int, default=5)
    parser.add_argument('-M','--adc_max',  help='max adc value for MIP peak',  type=int, default=100)
    parser.add_argument('-t','--trigtime', help='trigtime',                    type=int, default=92, nargs='+')
    parser.add_argument('-g','--gain',     help='gain',                        type=int, required=True )
    args = parser.parse_args()

    adcmin=args.adc_min
    adcmax=args.adc_max
    nbins=(adcmax-adcmin)
    
    eta=2

    reader = an.reader( filename=args.infile, treename='hgcalhit/hits' )
    data = reader.df

    chip,half,channel,rocchannel,channeltype = pad2ElecID(args.pad)
    print(f'pad {args.pad}, chip {chip}, half: {half}, channel: {channel}, rocchannel: {rocchannel}, channeltype: {channeltype}')
    
    fig, ax = plt.subplots(figsize=(10,10))
    for axis in ['top','bottom','left','right']:
        ax.spines[axis].set_linewidth(2)
    ax.tick_params(width=2)
    ax.grid(linewidth=1.5)
    ax.xaxis.grid(True)
    ax.yaxis.grid(True)

    data = data[ (data['chip']==chip) & (data['channel']==channel) & (data['half']==half) ]
    data = data[ data['trigtime'].isin(args.trigtime) ]
    data=data.sort_values(by=['adc'],ignore_index=True)
    mipdata = data[ (data['adc']<adcmax) & (data['adc']>adcmin) ]
    peddata = data[ (data['adc']<adcmin) ]

    p = peddata['adc'].to_numpy()
    pfreqs, pvals = np.histogram(p,adcmin*2,range=[-adcmin, adcmin])
    pvals=pvals[:-1]
    pprint(pfreqs)
    pprint(pvals)
    pcoeff, ppcov = curve_fit(gaussian, pvals, pfreqs,
                              absolute_sigma=True,
                              p0=(10, p.mean(), p.std()) )



    x = mipdata['adc'].to_numpy()
    freqs, xvals = np.histogram(x,nbins,range=[adcmin, adcmax])
    xvals=xvals[:-1]
    pprint(freqs)
    pprint(xvals)
    print(freqs.max(),freqs.argmax(),xvals[freqs.argmax()])
    mpv = xvals[freqs.argmax()]
    A = freqs.max()
    sigma = abs(pcoeff[2])
    coeff, pcov = curve_fit(pylandau.langau, xvals, freqs,
                            absolute_sigma=True,
                            p0=(mpv, eta, sigma, A) )


    plt.errorbar(pvals, pfreqs, np.sqrt(gaussian(pvals, *pcoeff)), fmt=".")
    manyvals = np.linspace(-adcmin,adcmax,1000)
    plt.plot(manyvals, gaussian(manyvals, *pcoeff), "-")

    plt.errorbar(xvals, freqs, np.sqrt(pylandau.langau(xvals, *coeff)), fmt=".")
    landaus = np.linspace(adcmin,adcmax,1000)
    plt.plot(landaus, pylandau.langau(landaus, *coeff), "-")

    plt.title(f'Silicon pad {args.pad}, ADC range = {args.gain} fC',size=20)
    plt.xlabel(r'Signal [ADC counts]')
    plt.ylabel(r'# events')
        
    outdir,_ = os.path.split(args.infile)
    
    row = [[ args.pad, chip, rocchannel, channeltype, 
            coeff[0]-pcoeff[1], 
            coeff[1],
            abs(pcoeff[2]),
            (coeff[0]-pcoeff[1])/abs(pcoeff[2]),
             args.gain ]]
    outdf = pandas.DataFrame(row, columns=['pad','chip','channel','channeltype','mip','eta','noise','SoN','gain'])
    print(outdf)
    outfile = outdf.to_hdf(f'{outdir}/pad{args.pad}.h5', key='mip', mode='w')
    
    plt.text( 0.55, 0.90, r'MIP = $%4.3f$ [ADC counts]'%outdf['mip'].max(),transform = ax.transAxes,size=18)
    plt.text( 0.55, 0.85, r'S/N = $%4.3f$'%outdf['SoN'].max(),transform = ax.transAxes,size=18)
    
    plt.savefig(f'{outdir}/pad{args.pad}.png',format='png',bbox_inches='tight')

