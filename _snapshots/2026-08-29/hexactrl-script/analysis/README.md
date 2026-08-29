# Hexactrl Analysis

Analysis scripts for data from HGCROC-based devices.

### Setup

To set up the `PYTHONPATH`, please run:

```
source env.sh
```
### Code structure

 - [level0](level0/README.md): Analyses relying only on a single measurement (e.g., pedestal run). Contains all the current "online" analyses. 
    - **TODO**: 
        - integrate this back to `hexactrl-script` as a submodule
        - add the capability to (re-)run these analyses offline
        - produces summary files aggregating information from different measurements for `level1` analyses.

 - [level1](level1/README.md): Analyses relying on several measurements performed on the same single chip board / hexaboard (e.g., correlating calibDAC voltage - calibDAC code - injection scan). 

 - [level2](level2/README.md): Analyses cross comparing serveral single chip boards / hexaboards. Ideally with interactive plotting?

 - [workflow](workflow/README.md): Luigi-based workflows for `level0` and `level1` analyses, and report generation for each chip/hexaboard?

