"""Task queue implementation.

The task queue is what will allow the repo backup tool to run more efficiently 
by multithreading long-running tasks, especially Internet accesses.  The main 
program will read the configuration, and push the appropriate tasks onto the 
queue.  As those tasks run, if they have long-running parts to them, the 
completion of those parts can simply become additional tasks on the queue.

For example, a task that identifies all the remote GitHub repositories for an 
organization can create a new task to mirror each repository locally.  Then the
repo identifier task is complete.

As the mirroring tasks run, each one that identifies a submodule can create a
task to mirror that submodules.  And so on and so on until all the tasks
are complete, and then the program is done.
"""

import queue
import threading
import logging

log = logging.getLogger(__name__)

class SingleTaskQueue:
    """Single-threaded, simple implementation of a TaskQueue.
    
    Ideally this would be smartened up through the use of concurrent.futures
    and a ThreadPoolExecutor, but that's a job for later; this is easy for now.
    """
    
    def __init__(self):
        self._queue = []
        self._next_task = 1
    
    def append(self, task, *args, desc=None, **kwargs):
        """Append a task to the queue.
        
        Args:
            desc: Logging description for this task.
            
            Other arguments are passed to the task when called.
        """
        
        if desc is None:
            desc = f'task_{self._next_task}'
        log.debug("Queuing {%s}", desc)
        self._next_task += 1
        self._queue.append((task, desc, args, kwargs))

    def runall(self):
        """Executes all events in the queue.
        
        This includes new events added to the queue by events in the queue.
        """
        while self._queue:
            (task, desc, args, kwargs) = self._queue.pop(0)
            log.debug("Executing {%s,%s,%s}", desc, args, kwargs)
            task(*args, **kwargs)
            log.debug("Completed {%s}", desc)
            
    def __len__(self):
        return len(self._queue)

class _TerminateThread(Exception):
    pass

class ThreadedTaskQueue:
    """Multi-threaded implementation of a TaskQueue.

    Args:
        max_tasks: Maximum number of simultaneous tasks to execute.

    """
    
    def __init__(self, max_tasks:int = 4):
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._next_task = 1
        self._threads = [
            threading.Thread(target=self._runthread, daemon=False)
                for _ in range(max_tasks)
        ]
    
    def append(self, task, *args, desc=None, **kwargs):
        """Append a task to the queue.
        
        Args:
            desc: Logging description for this task.
            
            Other arguments are passed to the task when called.
        """
        
        if desc is None:
            desc = f'task_{self._next_task}'
        log.debug("Queuing {%s}", desc)

        with self._lock:
            self._next_task += 1
        self._queue.put((task, desc, args, kwargs))

    def _killthread(self):
        raise _TerminateThread()

    def _runthread(self):
        """Executes queue events while possible."""

        while True:
            try:
                (task, desc, args, kwargs) = self._queue.get()
                log.debug("Executing {%s,%s,%s}", desc, args, kwargs)
                task(*args, **kwargs)
            except _TerminateThread:
                break
            except Exception:
                log.exception('unhandled exception')
            finally:
                self._queue.task_done()
                log.debug("Completed {%s}, %d items in queue", desc, len(self))
        
        log.debug('Terminating thread')
    
    def runall(self):
        """Executes all events in the queue.  Run from main thread.
        
        This includes new events added to the queue by events in the queue.
        """
        
        # Run all the threads, and the entire queue through to completion
        for t in self._threads:
            t.start()
        self._queue.join()

        # Send all the threads a termination notice
        for n, t in enumerate(self._threads):
            self.append(self._killthread, desc=f'Terminate {n}')
        
        # And wait for them to complete
        for t in self._threads:
            t.join()
            
    def __len__(self):
        return self._queue.qsize()

_tq = ThreadedTaskQueue()

def taskqueue():
    """Return the global TaskQueue."""
    return _tq
