from linkrottie.taskqueue import taskqueue
from collections import Counter
from threading import Lock

ctr = Counter()
lock = Lock()

def task(n:int):
	tq = taskqueue()
	if n < 10:
		tq.append(task, n+1, desc=f"Task {n}+1")
		tq.append(task, n*2, desc=f"Task {n}*2")
	
	with lock:
		ctr[n] += 1

def simulate_task(c:Counter, n:int):
	c[n] += 1
	if n < 10:
		simulate_task(c, n+1)
		simulate_task(c, n*2)

def test_taskqueue():
	test_counter = Counter()
	simulate_task(test_counter, 2)
	simulate_task(test_counter, 3)
	
	tq = taskqueue()
	tq.append(task, 2, desc="Initial task 2")
	tq.append(task, 3, desc="Initial task 3")
	tq.runall()
	
	assert test_counter.keys() == ctr.keys(), "Keys don't match"
	for k in sorted(test_counter):
		v = test_counter[k]
		print(f'[{k}] =  {v}')
		assert v == ctr[k], f"Key {k} expected {v}, got {ctr[k]}"

