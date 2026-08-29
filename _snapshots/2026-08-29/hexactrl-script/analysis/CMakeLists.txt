set(ana_source_dir ${PROJECT_SOURCE_DIR}/hexactrl-script/analysis) 

set( ANA_DESTINATION ${CTRL_DESTINATION}/analysis )

message(${ana_source_dir})
message(${ANA_DESTINATION})

install(FILES ${ana_source_dir}/etc/requirements.txt DESTINATION ${ANA_DESTINATION}/etc)
install(FILES ${ana_source_dir}/etc/env.sh DESTINATION ${ANA_DESTINATION}/etc)

file( GLOB level0
  ${ana_source_dir}/level0/analyzer.py
  ${ana_source_dir}/level0/pedestal_run_analysis.py
  ${ana_source_dir}/level0/vrefinv_scan_analysis.py
  ${ana_source_dir}/level0/vrefnoinv_scan_analysis.py
  ${ana_source_dir}/level0/vref2D_scan_analysis.py
  ${ana_source_dir}/level0/phase_scan_analysis.py
  ${ana_source_dir}/level0/delay_scan_analysis.py
  ${ana_source_dir}/level0/sampling_scan_analysis.py
  ${ana_source_dir}/level0/injection_scan_analysis.py  
  ${ana_source_dir}/level0/pedestal_scan_analysis.py
  ${ana_source_dir}/level0/toa_trim_scan_analysis.py
  ${ana_source_dir}/level0/toa_vref_scan_analysis.py
  ${ana_source_dir}/level0/toa_vref_scan_noinj_analysis.py
  )
message("source form analysis/level0: ${level0}")
install(FILES ${level0} DESTINATION ${ANA_DESTINATION}/level0 )
