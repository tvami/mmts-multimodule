#!/usr/bin/python
from common import *
import simple_daq_dacb

start_cm = 0
start_ch = 0
cm_dacb = []
ch_dacb = []
step_cm = 2
step_ch = 2
gain_conv = 12

def acq(n_events, indir):
    simple_daq_dacb.acq(n_events, indir)


def dacb_loop_cm(n_events, indir):
    odir = indir + "/dacb_cm"
    odir = os.path.abspath(odir) + "/"
    if not os.path.exists(odir): os.makedirs(odir)

    dacbs = range(start_cm,64,step_cm)

    for SignDac in range(1): # 2
        print "Setting Sign_dac for CM channels to %i" %SignDac
        set_roc_parameter(df_params, "cm", 1,"Sign_dac", SignDac)
        set_roc_parameter(df_params, "cm", 3,"Sign_dac",SignDac)
        for dacb in dacbs:
            print "Setting dacb for CM channels to %i" %dacb
            set_roc_parameter(df_params, "cm", 1,"Dacb", dacb)
            set_roc_parameter(df_params, "cm", 3,"Dacb", dacb)
            label = (2*SignDac-1)*dacb
            outdir = odir + "dacb_%i" %(label)
            outdir = os.path.abspath(outdir) + "/"

            if not os.path.exists(outdir):
                os.makedirs(outdir)

            acq(n_events, outdir)

    return odir


def dacb_loop(n_events, indir):
    odir = indir + "/dacb_ch"
    odir = os.path.abspath(odir) + "/"
    if not os.path.exists(odir): os.makedirs(odir)

    dacbs = range(start_ch,64,step_ch)

    for SignDac in range(1): # 2 default
        print "Setting Sign_dac for all the channels to %i" %SignDac
        set_roc_parameter(df_params, "ch", "all","Sign_dac", SignDac)
        for dacb in dacbs:
            print "Setting dacb for all channels to %i" %dacb
            set_roc_parameter(df_params, "ch", "all","Dacb", dacb)
            #set_roc_parameter(df_params, "ch", 24,"Dacb", dacb)
            #set_roc_parameter(df_params, "ch", 54,"Dacb", dacb)
            label = (2*SignDac-1)*dacb
            outdir = odir + "dacb_%i" %(label)
            outdir = os.path.abspath(outdir) + "/"

            if not os.path.exists(outdir):
                os.makedirs(outdir)

            acq(n_events, outdir)

    return odir


def set_cm(df_chans,cm):
    '''
    channels: cm1,Cm0,cm2,cm3
    N dataframe: -3,-2,73,74
    index dataframe: 0, 1, 2, 3
    '''
    print("Searching the closest dacb value giving pedestal to %i for cm1" %cm[0])
    sel = df_chans.channel == -3
    sel &= df_chans.adc > cm[0] - 0 #5
    df_sel = df_chans[sel]    
    target = cm[0]
    adc_vs_dacb = df_sel.groupby("dacb")["adc"].agg("mean")
    print adc_vs_dacb
    ret =int(abs(adc_vs_dacb - target).index.values[abs(adc_vs_dacb - target).values.argmin()])
    print ret
    if ret < 1:
        SignDac = 0
    else:
        SignDac = 1
    print("Setting Sign_dac to %i and dacb to %i" %(SignDac,abs(ret)))
    set_roc_parameter(df_params, "cm", 1,"Dacb", abs(ret))
    set_roc_parameter(df_params, "cm", 1,"Sign_dac", SignDac)
    cm_dacb.append(ret)

    print("Searching the closest dacb value giving pedestal to %i for cm3" %cm[3])
    sel = df_chans.channel == 74
    sel &= df_chans.adc > cm[3] - 0 #5
    df_sel = df_chans[sel]
    target = cm[3]
    adc_vs_dacb = df_sel.groupby("dacb")["adc"].agg("mean")
    print adc_vs_dacb
    ret = int(abs(adc_vs_dacb - target).index.values[abs(adc_vs_dacb - target).values.argmin()])
    print ret
    if ret < 1:
        SignDac = 0
    else:
        SignDac = 1
    print("Setting Sign_dac to %i and dacb to %i" %(SignDac,abs(ret)))
    set_roc_parameter(df_params, "cm", 3,"Dacb", abs(ret))
    set_roc_parameter(df_params, "cm", 3,"Sign_dac", SignDac)
    cm_dacb.append(ret)



def set_ch(df_chans,chan,val):
    print("Searching the closest dacb value giving pedestal to %i for ch %i" %(val,chan))
    sel = df_chans.channel == chan
    #sel &= df_chans.adc > val - 0 #5
    df_sel = df_chans[sel]    
    target = val
    adc_vs_dacb = df_sel.groupby("dacb")["adc"].agg("mean")
    print adc_vs_dacb
    ret = int(abs(adc_vs_dacb - target).index.values[abs(adc_vs_dacb - target).values.argmin()])
    print ret
    if ret < 1:
        SignDac = 0
    else:
        SignDac = 1
    print("Setting Sign_dac to %i and dacb to %i" %(SignDac,abs(ret)))
    set_roc_parameter(df_params, "ch", chan,"Dacb", abs(ret))
    set_roc_parameter(df_params, "ch", chan,"Sign_dac", SignDac)
    ch_dacb.append(ret)


def main():
    n_events = 30
    suffix = ""
    
    print("Resetting Gain_conv to 0 and Dacb for all channels to 63")
    print(80*"#")
    set_roc_parameter(df_params, "GlobalAnalog", "all","Gain_conv", 0)
    set_roc_parameter(df_params, "ch", "all","Dacb", 63)
    set_roc_parameter(df_params, "cm", "all","Dacb", 63)
    set_roc_parameter(df_params, "calib", "all","Dacb", 63)
    set_roc_parameter(df_params, "ReferenceVoltage", "all","Toa_vref", 1023)
    set_roc_parameter(df_params, "ReferenceVoltage", "all","Tot_vref", 1023)


    
    print sys.argv

    if len(sys.argv) > 1:
        n_events = int(sys.argv[1])
        print("## %i events requested" %n_events)
    if len(sys.argv) > 2:
        suffix = "_" + str(sys.argv[2])
        print("## %s suffix requested" %suffix)


    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    indir = "./data/dacb/run_" + timestamp + suffix
    indir = os.path.abspath(indir) + "/"
    if not os.path.exists(indir): os.makedirs(indir)
    print "Output dir:"
    print indir
    odir = indir + "/first"
    acq(n_events, odir)
    channels, cm, calib = plot_data_dacb.main(odir)

    print channels
    print cm
    print calib
    

    print("Setting Gain_conv to %i" %gain_conv)
    print(80*"#")
    set_roc_parameter(df_params, "GlobalAnalog", "all","Gain_conv", gain_conv)

    print("Making dacb loop for both common-mode channels")
    odir = dacb_loop_cm(n_events, indir) 
    print("Processing the data .........")
    df_chans = data_process.main(odir)    
    set_cm(df_chans, cm)

    
    print
    print("Making dacb loop for all channels")
    print(80*"#")
    odir = dacb_loop(n_events, indir) 
    print("Processing the data ........")
    df_chans = data_process.main(odir)    
    for ch in range(len(channels)):
        print("Channels %i" %ch)
        set_ch(df_chans, ch, channels[ch])
    
    print
    print("Checking ............")
    odir = indir + "/second"
    acq(n_events, odir)
    channels2, cm2, calib2 = plot_data_dacb.main(odir)

    print channels2
    print cm2
    print calib2

    f= open(indir + "cm_dacb.txt","w+")
    f.write(str(cm_dacb))
    f.close()
    f= open(indir + "ch_dacb.txt","w+")
    f.write(str(ch_dacb))
    f.close()
    

if __name__ == "__main__":

    main()


