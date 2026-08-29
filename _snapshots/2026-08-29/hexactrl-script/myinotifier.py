import pyinotify,time
import glob, re, os 
import subprocess
import threading
import yaml
import util
from time import sleep, monotonic
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

    def stop(self, grace=30.0):
        """Shut down, but only after the last .raw has actually been picked up.

        stopUnpackerServer() joins the unpacker threads, so once a thread exists
        the data is safe.  The race is one step earlier: pyinotify may not have
        DELIVERED the IN_CLOSE_WRITE for the final .raw by the time the caller
        calls stop().  The unpacker server loop then exits before consuming it,
        no thread is ever started, there is nothing to join, and the caller's
        mergeData() runs against a directory with no .root in it.

        Symptoms that fix: no <run>.log written at all, `hadd could not validate
        argument .../*.root`, and crash_report.log saying
        "No such file or directory: /dev/shm/tmp<timestamp>.root".

        So: wait for at least one run to be seen, then for the queue to drain,
        before tearing anything down.  `grace` bounds the wait so a run that
        legitimately produced no raw file cannot hang the caller.
        """
        self.logger.debug(f'Stopping mylittleInotifier')

        deadline = monotonic() + grace

        # Fast path: give pyinotify a moment to deliver the last CLOSE_WRITE.
        for _ in range(30):
            if self.handler.fruns:
                break
            sleep(0.1)

        # Fallback: on some filesystems the event never arrives at all.  Docker
        # Desktop bind mounts on macOS are one -- the .raw is written by
        # daq-client inside the container and lands on disk, but no inotify
        # event is delivered, so the handler never sees it (observed
        # 2026-08-25: raw present 30s before the notifier gave up waiting).
        # Scan the output directory and queue anything the watch missed.
        for fraw in sorted(glob.glob(os.path.join(self.odir, '*.raw'))):
            frun = fraw[:-len('.raw')]
            if not os.path.exists(frun + '.yaml'):
                continue                      # metadata not written yet
            with self.handler._EventHandler__lock:
                if frun in self.handler.fruns:
                    continue
                self.handler.fruns.append(frun)
            self.logger.warning(
                f'inotify missed {os.path.basename(fraw)} -- queueing it from '
                f'a directory scan')
            self.handler.inputs.put(frun)

        if not self.handler.fruns:
            self.logger.warning(
                'no raw file found -- stopping anyway; expect no .root and a '
                'failed analysis')
        else:
            while not self.handler.inputs.empty() and monotonic() < deadline:
                sleep(0.1)
            if not self.handler.inputs.empty():
                self.logger.warning(
                    f'unpacker queue still not drained after {grace}s')

        self.handler.stopUnpackerServer()   # joins the unpacker threads
        self.notifier.stop()
        self.logger.info(f'Quit mylittleInotifier')
