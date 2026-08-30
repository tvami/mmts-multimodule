# Bench-local configs

Configs that belong to this bench rather than to the collaboration, kept out of
the `hexactrl-script` MR deliberately. The **run** configs that are bench-proven
live upstream on `tvami/hexactrl-script`, branch `mmts-alabama-configs`.

Copy into `hexactrl-sw/hexactrl-script/configs/` to use; that directory is a
submodule working tree and nothing there is tracked.

| file | what it is |
|---|---|
| `linkprobe_mux{A,B,C}_v3d.yaml` | link-presence probe, v3D ROCs |
| `linkprobe_mux{B,C}_v3c.yaml` | link-presence probe, v3C ROCs |
| `initLD-BT-3b_muxC_ped.yaml` | ⚠️ **PREDICTED**, never measured |

**Link probes** instrument all 6 DAQ and all 12 trigger capture blocks so a delay
scan reports which ones carry a stream. Delay scan only, never a pedestal. The
gate FAILs by design: unused links read `ngood 0`. Read the per-link list, not
the verdict. `v3c`/`v3d` is the ROC revision from character 7 of the module
serial, and sets `Top.in_inv_cmd_rx` (v3C → 1, v3D → 0).

They are excluded from the MR because they are diagnostics rather than data-taking
configs, and are mechanically derivable from a run config by enabling every link.

`initLD-BT-3b_muxC_ped.yaml` is excluded because **no LD Bottom has run in slot
C**. Its trigger set is a prediction from slots A and B; run
`linkprobe_muxC_v3d.yaml` and check the gate before trusting it. Missing and not
yet built: `linkprobe_muxA_v3c.yaml`.
