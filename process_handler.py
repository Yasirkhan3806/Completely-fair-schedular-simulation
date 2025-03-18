import random
import time
import multiprocessing
import psutil
import os
from multiprocessing import Manager
import math
from collections import deque

class ProcessCreate:
    def __init__(self):
        self.vRuntime = 0
        self.time_slice = 0
        self.weight = 0
        self.manager = Manager()
        self.paused_event = self.manager.Event()
        self.paused_event.clear()

    def worker(self):
        p = psutil.Process(os.getpid())
        p.cpu_affinity([0])
        while True:
            if self.paused_event.is_set():
                self.paused_event.wait()
            time.sleep(3)  # Simulate process execution

    def calculate_time_slice(self, p_weight, total_weight, target_latency=10):
        return (p_weight / total_weight) * target_latency

    def calculate_vRuntime(self, p_weight, total_weight):
        time_slice = self.calculate_time_slice(p_weight, total_weight)
        weight_factor = (1024 / p_weight)
        self.vRuntime += math.ceil(time_slice) * weight_factor
        return self.vRuntime, time_slice

    def weight_calculate(self, niceness):
        weights = {
            -10: 9548, -5: 3121, 0: 1024, 5: 335, 10: 110
        }
        self.weight = weights.get(niceness, 1024)  # Default to 1024 if niceness not found

class Scheduler:
    def __init__(self, notify_queue):
        self.process_list = []
        self.total_weight = 0
        self.notify_queue = notify_queue  # Shared queue for communication

    def add_processes(self, process_names=[], weights=[]):
        for i in range(len(process_names)):
            p = ProcessCreate()
            process = multiprocessing.Process(target=p.worker)
            p.weight_calculate(weights[i])
            self.total_weight += p.weight
            print(f"Adding process {process_names[i]}")
            self.process_list.append({
                "name": process_names[i],
                "process": process,
                "process_obj": p,
                "weight": p.weight,
                "paused_event": p.paused_event,
                "exe_time": random.randint(0, 10)
            })

    def run_scheduler(self, process_names=[], weights=[]):
        self.add_processes(process_names, weights)

        for process in self.process_list:
            process["vRuntime"], process["time_slice"] = process["process_obj"].calculate_vRuntime(process["weight"], self.total_weight)

        for process in self.process_list:
            process["process"].start()
            process["paused_event"].set()  # Start paused

        while len(self.process_list) > 0:
            self.process_list.sort(key=lambda x: x["vRuntime"])
            process = self.process_list[0]
            print(f"Running process: {process['name']} (Time Slice: {process['time_slice']:.2f}s)")
            
            process["paused_event"].clear()
            self.notify_queue.put(process["name"])  # Push to queue
            time.sleep(process["time_slice"])

            process["paused_event"].set()
            process["vRuntime"], _ = process["process_obj"].calculate_vRuntime(process["weight"], self.total_weight)
            print(f"Process {process['name']} vRuntime: {process['vRuntime']}")

            if process["vRuntime"] > process["exe_time"]:
                process["process"].terminate()
                self.process_list.remove(process)
                print(f"Process {process['name']} terminated.")
            else:
                print(f"Process {process['name']} paused.")

