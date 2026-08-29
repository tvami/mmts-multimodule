cmake_minimum_required(VERSION 2.6 FATAL_ERROR)
project( tbtester )

set( CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11 -lzmq -lyaml-cpp -Wall -fPIC" )
list(APPEND CMAKE_PREFIX_PATH $ENV{ROOTSYS})
list( APPEND CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake )

find_package( Boost COMPONENTS thread system filesystem timer REQUIRED )
find_package( CACTUS REQUIRED )
find_package( SWIG REQUIRED )

INCLUDE(${SWIG_USE_FILE})

set(PYTHON_INCLUDE_PATH /usr/include/python3.6m)
set(PYTHON_LIBRARIES /usr/lib64/libpython3.6m.so)
set(PYTHON_EXECUTABLE /usr/bin/python3.6m)
set(PYTHON_INCLUDE_DIR /usr/include/python3.6m)

include_directories( SYSTEM ${CMAKE_CURRENT_SOURCE_DIR}/sources/main/include ${Boost_INCLUDE_DIRS} ${UHAL_LOG_INCLUDE_PREFIX} ${UHAL_GRAMMARS_INCLUDE_PREFIX} ${UHAL_UHAL_INCLUDE_PREFIX} ${PYTHON_INCLUDE_PATH})
link_directories( ${link_directories} ${EXTERN_BOOST_LIB_PREFIX} ${UHAL_LOG_LIB_PREFIX} ${UHAL_GRAMMARS_LIB_PREFIX} ${UHAL_UHAL_LIB_PREFIX} )

file( GLOB sources ${PROJECT_SOURCE_DIR}/sources/main/src/*.cc )
file( GLOB headers ${PROJECT_SOURCE_DIR}/sources/main/include/*.h )
file( GLOB executables ${PROJECT_SOURCE_DIR}/sources/main/executables/*.cxx )

message( "-- Main executables to be installed")
foreach( exec ${executables} )
	 message( "\t${exec}" )
	 get_filename_component(ex ${exec} NAME_WE)
	 add_executable( ${ex} ${exec} ${sources} ${headers} )
	 target_link_libraries( ${ex} ${Boost_LIBRARIES} boost_program_options boost_regex boost_serialization boost_chrono cactus_uhal_log cactus_uhal_grammars cactus_uhal_uhal )
	 install( TARGETS ${ex} DESTINATION ${PROJECT_SOURCE_DIR}/bin
          	  ARCHIVE DESTINATION ${PROJECT_SOURCE_DIR}/lib
		  LIBRARY DESTINATION ${PROJECT_SOURCE_DIR}/lib )
endforeach()

add_library( ${PROJECT_NAME} SHARED ${sources} )
target_link_libraries( ${PROJECT_NAME} ${Boost_LIBRARIES} boost_program_options boost_regex boost_serialization boost_chrono cactus_uhal_log cactus_uhal_grammars cactus_uhal_uhal )
target_include_directories( ${PROJECT_NAME} PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include )
install( TARGETS ${PROJECT_NAME}
         ARCHIVE DESTINATION ${PROJECT_SOURCE_DIR}/lib
	 LIBRARY DESTINATION ${PROJECT_SOURCE_DIR}/lib )

set(CMAKE_SWIG_FLAGS "")

set_source_files_properties(sca.i PROPERTIES CPLUSPLUS ON)
set_property(SOURCE sca.i PROPERTY SWIG_FLAG "-includeall" "-py3")
swig_add_module(sca python sca.i ${PROJECT_SOURCE_DIR}/sources/main/src/gbtsca.cc)
swig_link_libraries(sca ${PYTHON_LIBRARIES} ${Boost_LIBRARIES} boost_program_options boost_regex boost_serialization boost_chrono cactus_uhal_log cactus_uhal_grammars cactus_uhal_uhal tbtester)



