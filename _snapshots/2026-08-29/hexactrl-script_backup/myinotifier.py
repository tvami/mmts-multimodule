import pyinotify,time
import glob, re, os 
import subprocess
import threading
import yaml
import util
from time import sleep
import logging
from queue import Queue

class EventHandler(pyinotify.ProcessEvent):
    def __init__(self):
        self.inputs = Queue()
        self.fruns = []
        self.__lock = threading.Lock()  
        self.threads=[]
        self.master_thread=None
        self.logger = logging.getLogger('inotifierHandler')
        self.logger.debug("initialize inotifier handler")
        self.stop = False

    def process_IN_CLOSE_WRITE(self, event):
        self.logger.info(f'WRITING: {event.pathname}')
        with self.__lock:
            frun=''
            if event.pathname.find('.raw')>0:
                frun = event.pathname.split('.raw')[0]
            elif event.pathname.find('.yaml')>0:
                with open(event.pathname) as fin:
                    yamlnode = yaml.safe_load(fin)
                    if 'metaData' in yamlnode.keys():
                        frun = event.pathname.split('.yaml')[0]
            if frun!='' and frun not in self.fruns:
                self.inputs.put(frun)
                self.fruns.append(frun)

    def __run_unpacker(self,fin,fout,fmeta,flog):
        while True:
            if os.path.exists(fin) and os.path.exists(fmeta):
                break
            else:
                self.logger.debug(f'missing raw or yaml file to start the unpacker -> wait 0.01 sec')
                sleep(0.01)

        cmd='unpack -i ' + fin + ' -o ' + fout + ' -M ' + fmeta
        self.logger.info(f'STARTING:\t {cmd}')
        with open(flog,'w') as logout:
            subprocess.run( cmd, shell=True, stderr=logout,stdout=logout  )

    def __unpacker_server(self):
        counter=0
        while self.stop!=True:
            try:
                frun = self.inputs.get(timeout=.5)
                counter = counter + 1
                fraw = f'{frun}.raw'
                fmeta = f'{frun}.yaml'
                fout = f'{frun}.root'
                flog = f'{frun}.log'
                self.logger.debug(f'got {fraw} and {fmeta}')
                x = threading.Thread( target = self.__run_unpacker, args=(fraw,fout,fmeta,flog) )
                x.start()
                self.threads.append(x)
            except:
                pass
        self.logger.debug(f'{counter} threads have been started')
                
    def startUnpackerServer(self):
        self.logger.debug(f'Start unpacker thread')
        self.master_thread = threading.Thread( target = self.__unpacker_server )
        self.master_thread.start()
        with self.__lock:
            self.stop = False

    def stopUnpackerServer(self):
        self.logger.debug(f'Stop unpacker thread')
        with self.__lock:
            self.stop = True
        for x in self.threads:
            x.join()
            self.logger.debug(f'After join check if thread is alive : {x.is_alive()}')
        self.master_thread.join()
        self.logger.debug(f'Unpacker server thread stopped')

class mylittleInotifier:
    def __init__(self,odir="./",logging_level='INFO'):
        self.odir = odir
        self.handler = EventHandler()

        self.wm = pyinotify.WatchManager()  # Watch Manager
        self.mask = pyinotify.IN_CLOSE_WRITE # watched events
        self.notifier = pyinotify.ThreadedNotifier(self.wm, self.handler)
        self.logger = logging.getLogger('mylittleInotifier')
        util.setLoggingLevel(logging_level,'inotifierHandler')
        util.setLoggingLevel(logging_level,'mylittleInotifier')

    def start(self):
        self.logger.info(f'Starting mylittleInotifier')
        self.notifier.start()
        wdd = self.wm.add_watch(self.odir, self.mask, rec=False)
        self.handler.startUnpackerServer()

    def stop(self):
        self.logger.debug(f'Stopping mylittleInotifier')
        self.handler.stopUnpackerServer()
        # self.notifier.join()# wait half a second to let handler and analyzer processing last run
        self.notifier.stop()
        self.logger.info(f'Quit mylittleInotifier')
