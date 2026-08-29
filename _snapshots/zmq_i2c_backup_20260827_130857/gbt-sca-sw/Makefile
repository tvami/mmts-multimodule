# Set the project home directory to the current directory
MY_PROJECT_ROOT = $(shell pwd)

# The root folder for all the cactus
CACTUS_ROOT = /opt/cactus

# Include the headers in your project's include folder
INCLUDES = $(wildcard include/*.hpp)

# The include path is your own include directory and the cactus includes
INCLUDE_PATH =  \
                -Iinclude  \
                -I${CACTUS_ROOT}/include


# Set your library name here
LIBNAME = ipbusemulator

LIBRARY = lib/lib${LIBNAME}.so
LIBRARY_SOURCES = $(wildcard src/*.cpp)
LIBRARY_OBJECT_FILES = $(patsubst src/%.cpp,obj/%.o,${LIBRARY_SOURCES})

EXECUTABLE_SOURCES = $(wildcard src/*.cxx)
EXECUTABLE_OBJECT_FILES = $(patsubst src/%.cxx,obj/%.o,${EXECUTABLE_SOURCES})
EXECUTABLES = $(patsubst src/%.cxx,bin/%,${EXECUTABLE_SOURCES})

LIBRARY_PATH =  \
                -L${CACTUS_ROOT}/lib \
                -L${MY_PROJECT_ROOT}/lib 


LIBRARIES =     \
                -lpthread \
                \
                -lboost_filesystem \
                -lboost_regex \
                -lboost_system \
                -lboost_thread \
                -lboost_timer \
                -lboost_random \
		-lboost_program_options \
                \
		-lcactus_uhal_log \
                -lcactus_uhal_grammars \
                -lcactus_uhal_uhal

#-lcactus_extern_pugixml 
CPP_FLAGS = -O3 -Wall -fPIC -std=c++11 -g ${INCLUDE_PATH}
LINK_LIBRARY_FLAGS = -shared -fPIC -Wall -O3 ${LIBRARY_PATH} ${LIBRARIES}
LINK_EXECUTABLE_FLAGS = -Wall -g -O3 ${LIBRARY_PATH} ${LIBRARIES} -l${LIBNAME}

.PHONY: all _all build _buildall clean _cleanall

default: build

clean: _cleanall
_cleanall:
	rm -rf bin
	rm -rf obj
	rm -rf lib
  
all: _all
build: _all
buildall: _all
_all: obj bin lib ${LIBRARY} ${EXECUTABLES}

bin:
	mkdir -p bin

obj:
	mkdir -p obj

lib:
	mkdir -p lib

${EXECUTABLES}: bin/%: obj/%.o ${EXECUTABLE_OBJECT_FILES}
	g++ ${LINK_EXECUTABLE_FLAGS}  $< -o $@

${EXECUTABLE_OBJECT_FILES}: obj/%.o : src/%.cxx
	g++ -c ${CPP_FLAGS}  $< -o $@

${LIBRARY}: ${LIBRARY_OBJECT_FILES}
	g++ ${LINK_LIBRARY_FLAGS} ${LIBRARY_OBJECT_FILES} -o $@

${LIBRARY_OBJECT_FILES}: obj/%.o : src/%.cpp 
	g++ -c ${CPP_FLAGS} $< -o $@
