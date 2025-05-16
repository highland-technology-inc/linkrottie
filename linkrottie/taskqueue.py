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

import logging

log = logging.getLogger(__name__)

class TaskQueue:
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

	def runnext(self):
		"""Executes the next event from the queue.
		
		Raises IndexError if the queue is empty.
		"""
		
		(task, desc, args, kwargs) = self._queue.pop(0)
		log.debug("Executing {%s,%s,%s}", desc, args, kwargs)
		task(*args, **kwargs)
		log.debug("Completed {%s}", desc)
	
	def runall(self):
		"""Executes all events in the queue.
		
		This includes new events added to the queue by events in the queue.
		"""
		while self._queue:
			self.runnext()
			
	def __len__(self):
		return len(self._queue)

_tq = TaskQueue()

def taskqueue():
	"""Return the global TaskQueue."""
	return _tq
