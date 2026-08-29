import matplotlib.pyplot as plt

def plot_calibdac(data,outpath,dpi=250):
    for half in ['half0','half1']:
        fig,ax=plt.subplots(1,1)
        ax.set_title(half)
        ax.set_xlabel('calibdac value')
        ax.set_ylabel('voltage')
        for roc in data['node']['calib']:
            xs=[]
            ys=[]
            for i in data['node']['calib'][roc][half]:
                xs.append(i)
                ys.append(data['node']['calib'][roc][half][i])
            ax.plot(xs,ys,'.-',label=roc)
            ax.legend()
        fig.savefig(outpath+'calibdac_'+half+'.png',dpi=dpi)


def plot_probeDC(data,outpath,
            dc1_names = ["vbi_pa", "vbm_pa", "vbm2_pa", "vbm3_pa", "vbo_pa", "vb_inputdac",
                    "vbi_discri_tot", "vbm_discri_tot", "vbo_discri_tot", "vbi_discri_toa",
                    "vcasc_discri_toa", "vbm1_discri_toa", "vbm2_discri_toa", "vbo_discri_toa",
                    "EXT_REF_TDC", "probe_VrefCf", "vcn", "VD_FTDC_P_EXT", "VD_CTDC_P_EXT",
                    "probe_VrefPa", "vcp", "VD_FTDC_N_EXT", "VD_CTDC_N_EXT", "vb_hyst_tot", "vbi_itot_neg",
                    "vbi_itot_pos", "vbiN_sk", "vbiP_sk", "vbFCN_sk", "vbFCP_sk", "vbiN_noinv", "vbiP_noinv"],
            dc2_names = ["vbFCN_noinv", "vbFCP_noinv", "vbiN_inv", "vbip_inv", "vbFCN_inv", "vbFCP_inv", "vbiN_noinv_buf",
                    "vbiP_noinv_buf", "vbFCN_noinv_buf", "vbFCP_noinv_buf", "vbiN_inv_buf", "vbFCP_inv_buf",  
                    "vbiP_inv_buf", "vbFCN_inv_buf", "vb_5bdac_out_inv", "vb_5bdac_tot", "vb_5bdac_toa",
                    "vcm_0p6_inv", "vcm_0p6_noinv", "vref_adc", "vcm_adc", "Vref_sk", "Vref_noinv", "Vref_inv", 
                    "Vref_tot", "Vref_toa", "vbg_1v", "probe_center", "ibi_ref_adc", "ibo_ref_adc", "probe_vddd", 
                    "probe_vdda"],
            dpi=250):
    dc_titles=['dc1','dc2']
    dc_idx=0
    num_rocs = len(data['node'][dc1_names[0]])
    for dc in [dc1_names,dc2_names]:   
        for half in ['half0','half1']:
            ys=[]
            #set the right list structure for ys
            for i in range(num_rocs):
                ys.append([])
            for key in dc:
                rocidx=0
                for roc in data['node'][key]:
                    ys[rocidx].append(data['node'][key][roc][half])
                    rocidx+=1
            fig,ax=plt.subplots(1,1,figsize=(15,8))
            ax.set_title(dc_titles[dc_idx]+' '+half)
            ax.set_ylabel('voltage')
            for i in range(num_rocs):
                ax.plot(dc,ys[i],'.')
            ax.legend(['roc_s0','roc_s1','roc_s2'])
            plt.xticks(rotation=90)
            fig.tight_layout()
            fig.savefig(outpath+dc_titles[dc_idx]+' '+half+'.png',dpi=dpi,bbox_inches='tight')
        dc_idx+=1

if __name__ == "__main__":
    import yaml
    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option('-f','--FolderIn',
                        action='store', dest='FolderIn',
                        help='Folder containing input files')

    parser.add_option('-o','--FolderOut', default=None,
                        action='store', dest='FolderOut',
                        help='Folder to save output files to')

    (options, args) = parser.parse_args()
    if options.FolderOut==None:
        options.FolderOut=options.FolderIn

    f=open(options.FolderIn+'calibdac.yaml')
    calibdac_data=yaml.load(f,Loader=yaml.CLoader)
    f=open(options.FolderIn+'dc2_probe.yaml')
    probeDC_data=yaml.load(f,Loader=yaml.CLoader)

    plot_calibdac(calibdac_data,options.FolderOut)
    plot_probeDC(probeDC_data,options.FolderOut)