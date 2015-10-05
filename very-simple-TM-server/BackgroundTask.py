#Copyright 2015 Patrick Porter
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
## http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

#credit to http://tools.cherrypy.org/wiki/BackgroundTaskQueue
#adapted here for py3.4

import queue
import threading
import cherrypy
from cherrypy.process import plugins

class BackgroundTaskQueue(plugins.SimplePlugin):
    
    thread = None
    
    def __init__(self, bus, qsize=100, qwait=2, safe_stop=True):
        plugins.SimplePlugin.__init__(self, bus)
        self.q = queue.Queue(qsize)
        self.qwait = qwait
        self.safe_stop = safe_stop
    
    def start(self):
        self.running = True
        if not self.thread:
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
    
    def stop(self):
        if self.safe_stop:
            self.running = "draining"
        else:
            self.running = False
        
        if self.thread:
            self.thread.join()
            self.thread = None
        self.running = False
    
    def run(self):
        while self.running:
            try:
                try:
                    func, args, kwargs = self.q.get(block=True, timeout=self.qwait)
                except queue.Empty:
                    if self.running == "draining":
                        return
                    continue
                else:
                    func(*args, **kwargs)
                    if hasattr(self.q, 'task_done'):
                        self.q.task_done()
            except:
                self.bus.log("Error in BackgroundTaskQueue %r." % self,
                             level=40, traceback=True)
    
    def put(self, func, *args, **kwargs):
        """Schedule the given func to be run."""
        self.q.put((func, args, kwargs))