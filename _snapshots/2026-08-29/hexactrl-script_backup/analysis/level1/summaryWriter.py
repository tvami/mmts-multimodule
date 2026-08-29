# import level0.analyzer as analyzer
import glob

def writeSummary(odir,analyzer):
    files = glob.glob(odir+"/*.root")
    for f in files:
        analyzer.add(f)
        
    analyzer.mergeData()
    analyzer.addSummary()
    analyzer.writeSummary()
