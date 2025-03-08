import random
import time
import multiprocessing
import psutil
import os
from multiprocessing import Manager
import math

class ProcessCreate:
    def __init__(self):
        self.vRuntime = 0
        self.time_slice = 0
        self.weight = 0
        self.manager = Manager()  # Create a manager for shared objects
        self.paused_event = self.manager.Event()  # Use manager to create the event
        self.paused_event.clear()  # Start as not paused

    def worker(self):
        p = psutil.Process(os.getpid())  # Use psutil to get the current process
        p.cpu_affinity([0])  # Set CPU affinity to core 0
        while True:
            if self.paused_event.is_set():
                # print("Paused... Waiting to resume.")
                self.paused_event.wait()  # Wait until event is cleared (paused)
            # print("Running...")
            time.sleep(3)  # Simulate process execution

    def calculate_time_slice(self, p_weight, total_weight, target_latency=10):
        """ Calculate time slice based on CFS formula """
        return (p_weight / total_weight) * target_latency

    def calculate_vRuntime(self, p_weight, total_weight):
        """ Correct CFS formula for virtual runtime """
        time_slice = self.calculate_time_slice(p_weight, total_weight) 
        weight_factor = (1024 / p_weight)  
        self.vRuntime += math.ceil(time_slice) * weight_factor
        return self.vRuntime, time_slice  # Return both values

    def weight_calculate(self, niceness):
        """ Convert niceness to weight (CFS predefined values) """
        weights = {
            -10: 9548,
            -5: 3121,
            0: 1024,
            5: 335,
            10: 110
        }
        self.weight = weights[niceness]

class Scheduler:
    def __init__(self):
        self.process_list = []  # List of processes
        self.total_weight = 0  # Total weight of all processes

    def add_processes(self, process_names=[], weights=[]):
        """ Initialize processes with correct weights and time slices """
        for i in range(len(process_names)):
            p = ProcessCreate()  # Create a new instance for each process
            process = multiprocessing.Process(target=p.worker)  # Create the process
            
            p.weight_calculate(weights[i])  # Assign weight from niceness
            self.total_weight += p.weight  # Sum up total weight

            # Store event object inside dictionary
            self.process_list.append({
                "name": process_names[i],
                "process": process,
                "process_obj": p,  
                "weight": p.weight,
                "paused_event": p.paused_event,  # Store event for pausing
                "exe_time": random.randint(0, 10)  # Set execution time limit
            })

    def run_scheduler(self, process_names=[], weights=[]):
        """ Run CFS scheduling simulation """
        self.add_processes(process_names, weights)

        # Calculate initial vRuntime for all processes
        for process in self.process_list:
            process["vRuntime"], process["time_slice"] = process["process_obj"].calculate_vRuntime(process["weight"], self.total_weight)

        # Start all processes initially but keep them paused
        for process in self.process_list:
            process["process"].start()
            process["paused_event"].set()  # Start in paused state

        # Scheduler loop
        while len(self.process_list) > 0:
            # Sort processes by vRuntime (smallest runs first)
            self.process_list.sort(key=lambda x: x["vRuntime"])
            process = self.process_list[0]  # Pick process with smallest vRuntime
            
            print(f"Running process: {process['name']} (Time Slice: {process['time_slice']:.2f}s)")

            # Clear the pause event (allow process to run)
            process["paused_event"].clear()
            time.sleep(process["time_slice"])  # Simulate execution

            # Pause again after time slice ends
            process["paused_event"].set()

            # Update vRuntime after running
            process["vRuntime"], _ = process["process_obj"].calculate_vRuntime(process["weight"], self.total_weight)
            print(f"Process {process['name']} vRuntime: {process['vRuntime']}")
            # Check if process has exceeded its execution time
            if process["vRuntime"] > process["exe_time"]:
                process["process"].terminate()
                self.process_list.remove(process)
                print(f"Process {process['name']} terminated.")
            else:
                print(f"Process {process['name']} paused.")

if __name__ == "__main__":
    scheduler = Scheduler()
    scheduler.run_scheduler(["P1", "P2", "P3","P4"], [-5, 0, -10,-10])  # Test with different niceness values