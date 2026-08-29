import os, errno
import level0.analyzer as an
import matplotlib
#matplotlib.use('tkagg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.cm as cm

if __name__ == "__main__":

    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option("-f", "--inputfile", dest="inputfile",
                      help="data input file")

    parser.add_option("-o", "--odir", dest="odir",
                      help="output plot directory (will go to same dir as input file if not set)")

    (options, args) = parser.parse_args()
    print(options)

    if options.odir==None:
        odir = os.path.dirname(options.inputfile)
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

    nchip = len( data.groupby('chip').nunique() )        
    
    newdf = pd.DataFrame(  )
        
    for i in range(78*nchip):
        newdf[str(i)] = data[ data['chip']*78+data['half']*39+data['channel']==i ]['adc'].to_list()

    print( newdf )
    corr = newdf.corr()
    print( corr )
    
    mask = np.tril(np.ones_like(corr, dtype=np.bool))

    f, ax = plt.subplots(figsize=(18, 9))
    
    cmap = cm.get_cmap('bwr')

    sns.heatmap(corr, mask=mask, cmap=cmap, vmax=1., vmin=-1., center=0)
    ax.invert_yaxis()
    
    plt.title('Correlation')
    plt.xlabel(r'Channel ID')
    plt.ylabel(r'Channel ID ')
    
    plt.savefig('%s/correlation.png'%(odir))

    for chip in range(nchip):
        f, ax = plt.subplots(figsize=(18, 9))
        
        channels = [ str( i + chip*78 ) for i in range(78) ]
        chip_df = newdf[channels].copy()
        
        chip_df.columns = [ [ str( i ) for i in range(78) ] ]
        corr = chip_df.corr()
        mask = np.tril(np.ones_like(corr, dtype=np.bool))
        sns.heatmap(corr, mask=mask, cmap=cmap, vmax=1., vmin=-1., center=0)
        ax.invert_yaxis()

        plt.title('Correlation ASIC %d'%(chip))
        plt.xlabel(r'Channel ID')
        plt.ylabel(r'Channel ID')

        plt.savefig('%s/correlation_chip%d.png'%(odir,chip))
        
