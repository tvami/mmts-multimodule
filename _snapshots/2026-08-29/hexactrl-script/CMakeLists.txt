set(ctrl_source_dir ${PROJECT_SOURCE_DIR}/hexactrl-script) 

set( CTRL_DESTINATION ${DESTINATION}/ctrl )

file( GLOB configs
  ${ctrl_source_dir}/configs/init1ROC.yaml
  ${ctrl_source_dir}/configs/initLD-trophyV1.yaml
  ${ctrl_source_dir}/configs/initLD-trophyV2.yaml
  ${ctrl_source_dir}/configs/initLD-trophyV3.yaml
  ${ctrl_source_dir}/configs/initLD-trophyV3-3b.yaml
  ${ctrl_source_dir}/configs/initLD-semi.yaml
  ${ctrl_source_dir}/configs/initHD.yaml
  )
install(FILES ${configs} DESTINATION ${CTRL_DESTINATION}/etc/configs)
install(FILES ${ctrl_source_dir}/etc/requirements.txt DESTINATION ${CTRL_DESTINATION}/etc)
install(FILES ${ctrl_source_dir}/etc/env.sh DESTINATION  ${CTRL_DESTINATION}/etc)

file( GLOB python_source
  ${ctrl_source_dir}/zmq_controler.py
  ${ctrl_source_dir}/util.py
  ${ctrl_source_dir}/myinotifier.py
  ${ctrl_source_dir}/pedestal_run.py
  ${ctrl_source_dir}/pedestal_scan.py
  ${ctrl_source_dir}/vrefinv_scan.py
  ${ctrl_source_dir}/vrefnoinv_scan.py
  ${ctrl_source_dir}/vref2D_scan.py
  ${ctrl_source_dir}/phase_scan.py
  ${ctrl_source_dir}/sampling_scan.py
  ${ctrl_source_dir}/injection_scan.py
  ${ctrl_source_dir}/configure_rocs.py
  ${ctrl_source_dir}/delay_scan.py
  ${ctrl_source_dir}/toa_trim_scan.py
  ${ctrl_source_dir}/toa_vref_scan_noinj.py
  ${ctrl_source_dir}/toa_vref_scan.py
  ${ctrl_source_dir}/inCtest_run.py
  ${ctrl_source_dir}/probeDC_run.py
  ${ctrl_source_dir}/agilent_ctrl.py
  ${ctrl_source_dir}/PrologixEthernetAdapter.py
  ${ctrl_source_dir}/keithley2000_with_scanner_card.py
  ${ctrl_source_dir}/hb_prodtest.py
  ${ctrl_source_dir}/rocv3_prodtest.py
  )
message("source form hexacrl-script: ${python_source}")
install(FILES ${python_source} DESTINATION ${CTRL_DESTINATION} )
add_subdirectory(analysis)
