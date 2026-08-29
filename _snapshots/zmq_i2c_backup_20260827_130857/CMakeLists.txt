set(i2c_source_dir ${PROJECT_SOURCE_DIR}/zmq_i2c) 

file( GLOB regmaps ${i2c_source_dir}/reg_maps/*.pickle )
install(FILES ${regmaps} DESTINATION ${DESTINATION}/etc)
install(FILES requirements.txt DESTINATION ${DESTINATION}/etc)

file( GLOB python_source
  ${i2c_source_dir}/Boards.py
  ${i2c_source_dir}/Link.py
  ${i2c_source_dir}/ROC.py
  ${i2c_source_dir}/Translator.py
  ${i2c_source_dir}/zmq_server.py
  ${i2c_source_dir}/configure.py
  ${i2c_source_dir}/ADCinterfaces.py
  ${i2c_source_dir}/CMakeLists.txt
  )
message(${python_source})
install(FILES ${python_source} DESTINATION ${DESTINATION}/i2c )#Link.py configure.py ROC.py Translator.py zmq_server.py)
