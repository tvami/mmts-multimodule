# halves.py RUN_DIR... -- per-half adc_mean/adc_stdd from runsummary; flags FROZEN(n)
# when n channels in a half have adc_stdd == 0.  A frozen half passes CRC, finder and
# gate and reads as *quiet* in a noise map (slot A, 2026-09-02).  Run in the client
# container: docker run --rm --platform linux/amd64 -v $PWD:$PWD -w $PWD \
#   hexactrl-client:local "python3 $PWD/multimodule/bin/halves.py <run_dir>..."
# Note: on an HD Top or LD Five the sixth half (chip2 half1) has no link and always
# shows FROZEN(36); that one is expected.
import uproot, numpy as np, sys
for d in sys.argv[1:]:
    try:
        f=uproot.open(d+"/pedestal_run0.root"); t=f["unpacker_data/hgcroc"]
        s=f["runsummary/summary"].arrays(library="np")
    except Exception as e:
        print(d.split("/")[-1],"ERR",e); continue
    norm=s["channeltype"]==0
    row=[]
    for c in sorted(set(s["chip"].tolist())):
        for h in (0,1):
            m=norm&(s["chip"]==c)&(s["channel"]//36==h)
            if not m.sum(): continue
            mu=np.median(s["adc_mean"][m]); sd=np.median(s["adc_stdd"][m])
            nz=(s["adc_stdd"][m]==0).sum()
            row.append("%s%.0f/%.2f%s"%("",mu,sd," FROZEN(%d)"%nz if nz>18 else ""))
    print("%-22s nev=%d  %s"%(d.split("/")[-1], t.num_entries, "  ".join(row)))
