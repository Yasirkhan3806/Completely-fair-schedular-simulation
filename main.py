import random
import time
import multiprocessing
import psutil
import os
from multiprocessing import Manager
import math
from collections import deque
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import threading

class ProcessCreate:
    def __init__(self):
        self.vRuntime = 0
        self.time_slice = 0
        self.weight = 0
        self.manager = Manager()
        self.paused_event = self.manager.Event()
        self.shutdown_flag = self.manager.Event()
        self.paused_event.clear()
        self.shutdown_flag.clear()
        self.io_waiting = multiprocessing.Value('b', False)
        self.io_duration = multiprocessing.Value('d', 0.0)
        self.last_vruntime = multiprocessing.Value('d', 0.0)

    def worker(self):
        p = psutil.Process(os.getpid())
        try:
            while not self.shutdown_flag.is_set():
                if self.io_waiting.value:
                    time.sleep(self.io_duration.value)
                    self.io_waiting.value = False
                elif self.paused_event.is_set():
                    self.paused_event.wait()
                else:
                    if random.random() < 0.3:  # Increased I/O chance
                        self.io_waiting.value = True
                        self.io_duration.value = random.uniform(1, 2)
                    time.sleep(0.5)  # Reduced sleep time
        except (BrokenPipeError, ConnectionResetError):
            pass

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
        self.weight = weights.get(niceness, 1024)

class Scheduler:
    def __init__(self, notify_queue):
        self.process_list = []
        self.total_weight = 0
        self.notify_queue = notify_queue
        self.terminated_processes = set()
        self.io_queue = []

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
                "exe_time": random.randint(5, 15),
                "terminated": False
            })

    def run_scheduler(self, process_names=[], weights=[]):
        self.process_list = []
        self.total_weight = 0
        self.add_processes(process_names, weights)

        for process in self.process_list:
            process["vRuntime"], process["time_slice"] = process["process_obj"].calculate_vRuntime(process["weight"], self.total_weight)

        for process in self.process_list:
            process["process"].start()
            process["paused_event"].set()

        while len(self.process_list) > 0 or len(self.io_queue) > 0:
            self.handle_io_completion()
            if len(self.process_list) > 0:
                self.process_list.sort(key=lambda x: x["vRuntime"])
                process = self.process_list[0]
                self.handle_io(process)

                if process["name"] in self.terminated_processes:
                    self.process_list.remove(process)
                    continue

                print(f"Running process: {process['name']} (Time Slice: {process['time_slice']:.2f}s)")
                
                try:
                    process["paused_event"].clear()
                    self.notify_queue.put({
                        "name": process['name'],
                        "vRuntime": process['vRuntime'],
                        "time_slice": process['time_slice'],
                        "status": "running"
                    })
                    time.sleep(process["time_slice"])

                    process["paused_event"].set()
                    process["vRuntime"], _ = process["process_obj"].calculate_vRuntime(process["weight"], self.total_weight)
                    print(f"Process {process['name']} vRuntime: {process['vRuntime']}")

                    if process["vRuntime"] > process["exe_time"] and not process["terminated"]:
                        try:
                            if process["process"].is_alive():
                                process["process_obj"].shutdown_flag.set()
                                process["paused_event"].set()
                                process["process"].terminate()
                                process["process"].join()
                        except Exception as e:
                            print(f"Error terminating process {process['name']}: {e}")
                        
                        process["terminated"] = True
                        self.terminated_processes.add(process["name"])
                        self.notify_queue.put({"name": process["name"], "status": "terminated"})
                        self.process_list.remove(process)
                        print(f"Process {process['name']} terminated.")
                    else:
                        print(f"Process {process['name']} paused.")
                except Exception as e:
                    print(f"Error with process {process['name']}: {e}")
                    self.terminated_processes.add(process["name"])
                    self.notify_queue.put({"name": process["name"], "status": "terminated"})
                    self.process_list.remove(process)
                    print(f"Process {process['name']} removed due to error.")

    def handle_io_completion(self):
        completed = []
        for idx, process in enumerate(self.io_queue):
            if not process["process_obj"].io_waiting.value:
                process["vRuntime"] = process["process_obj"].last_vruntime.value
                self.process_list.append(process)
                completed.append(idx)
                self.notify_queue.put({"name": process['name'], "status": "io_complete"})
        
        for idx in reversed(completed):
            del self.io_queue[idx]

    def handle_io(self, process):
        if process["process_obj"].io_waiting.value:
            process["process_obj"].last_vruntime.value = process["vRuntime"]
            self.io_queue.append(process)
            self.process_list.remove(process)
            self.notify_queue.put({
                "name": process['name'],
                "status": "io_start",
                "duration": process["process_obj"].io_duration.value
            })

class Cube:
    vertices = [
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7)
    ]

    def __init__(self, position=(0, 0, 0), name="Cube"):
        self.position = position
        self.angle = 0
        self.name = name
    
    def draw(self):
        glPushMatrix()
        glTranslatef(*self.position)
        glRotatef(self.angle, 4, 2, 3)
        glBegin(GL_LINES)
        glColor3f(1, 1, 1)
        for edge in self.edges:
            for vertex in edge:
                glVertex3fv(self.vertices[vertex])
        glEnd()
        glPopMatrix()

    def rotate(self, allowed):
        if allowed:
            self.angle += 120

class Circle:
    def __init__(self, radius=3, num_segments=100, position=(0, 0, 0), name=""):
        self.radius = radius
        self.num_segments = num_segments
        self.position = position
        self.name = name
    
    def draw(self):
        glPushMatrix()
        glTranslatef(*self.position)
        glBegin(GL_LINE_LOOP)
        for i in range(self.num_segments):
            theta = 2.0 * math.pi * i / self.num_segments
            x = self.radius * math.cos(theta)
            y = self.radius * math.sin(theta)
            glVertex2f(x, y)
        glEnd()
        glPopMatrix()

class Scene:
    def __init__(self, process_list, weights, notify_queue):
        self.cubes = {}
        self.notify_queue = notify_queue
        self.scheduler = Scheduler(notify_queue)
        # self.scheduler.add_processes(process_list, weights)
        self.active_processes = process_list.copy()
        self.all_processes = process_list.copy()
        self.vRuntimes = {proc: 0.0 for proc in process_list}
        self.time_slices = {proc: 0.0 for proc in process_list}
        self.io_processes = {}
        
        for i, proc in enumerate(process_list):
            self.cubes[proc] = Cube(position=(i * 4, 0, 0), name=proc)
            self.cubes[f"{proc}_running"] = False
        
        self.circle = Circle(position=(3, 6, 0), name="CPU")
        self.io_circle = Circle(position=(12, 6, 0), name="I/O")

    def draw(self):
        for key, cube in self.cubes.items():
            if isinstance(cube, Cube) and key in self.active_processes:
                cube.draw()
        self.circle.draw()
        self.io_circle.draw()

    def draw_io_progress(self,render_callback, display):
        for i, (name, io) in enumerate(self.io_processes.items()):
            elapsed = time.time() - io["start_time"]
            progress = min(elapsed / io["duration"], 1.0)
            render_callback(
                f"{name} I/O: {progress*100:.1f}%", 
                (display[0] - 150, 50 + i*30)
            )

    def update(self):
        while True:
            try:
                message = self.notify_queue.get_nowait()
                process_name = message["name"]
                status = message["status"]
                
                if status == "running" and process_name in self.cubes:
                    self.vRuntimes[process_name] = message.get("vRuntime", 0)
                    self.time_slices[process_name] = message.get("time_slice", 0)
                    for key, cube in self.cubes.items():
                        if isinstance(cube, Cube):
                            if key == process_name and key in self.active_processes:
                                cube.position = (3, 6, 0)
                                cube.rotate(True)
                                self.cubes[f"{key}_running"] = True
                            elif key in self.active_processes:
                                cube.position = (self.active_processes.index(key) * 4, 0, 0)
                                cube.rotate(False)
                                self.cubes[f"{key}_running"] = False
                                
                elif status == "terminated" and process_name in self.active_processes:
                    if process_name in self.active_processes:
                        self.active_processes.remove(process_name)
                    self.reposition_cubes()

                if status == "io_start":
                    proc_name = message["name"]
                    if proc_name in self.cubes:
                        self.cubes[proc_name].position = (12, 6, 0)
                    self.io_processes[proc_name] = {
                        "start_time": time.time(),
                        "duration": message["duration"],
                        "progress": 0
                    }
                elif status == "io_complete":
                    proc_name = message["name"]
                    if proc_name in self.io_processes:
                        del self.io_processes[proc_name]
                    
            except:
                break

    def reposition_cubes(self):
        cpu_x, io_x, y_pos = 3, 12, 6
        for i, proc_name in enumerate(self.active_processes):
            if proc_name in self.cubes and isinstance(self.cubes[proc_name], Cube):
                if proc_name in self.io_processes:
                    self.cubes[proc_name].position = (
                        io_x + (i%2)*3, 
                        y_pos - (i//2)*3, 
                        0
                    )
                elif not self.cubes[f"{proc_name}_running"]:
                    self.cubes[proc_name].position = (i * 4, 0, 0)

class App:
    def __init__(self, process_list, niceness):
        pygame.init()
        self.display = (1200, 600)
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        gluPerspective(45, (self.display[0]/self.display[1]), 0.1, 50.0)
        glTranslatef(-4, -2, -20)
        
        self.manager = Manager()
        self.notify_queue = self.manager.Queue()
        self.scene = Scene(process_list, niceness, self.notify_queue)
        self.running = True
        self.font = pygame.font.Font(None, 24)
        
        self.scheduler_thread = threading.Thread(target=self.scene.scheduler.run_scheduler, args=(process_list, niceness))
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()

    def render_text(self, text, position):
        text_surface = self.font.render(text, True, (255, 255, 255))
        text_data = pygame.image.tostring(text_surface, "RGBA", True)
        glPushMatrix()
        glLoadIdentity()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, self.display[0], self.display[1], 0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glRasterPos2f(position[0], position[1])
        glDrawPixels(text_surface.get_width(), text_surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)
        glDisable(GL_BLEND)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def run(self, process_list=[]):
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    self.running = False

            self.scene.update()
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.scene.draw()

            # Render labels
            cpu_pos = self.project(3, 6, 0)
            self.render_text("CPU", (cpu_pos[0]-20, cpu_pos[1]-110))
            io_pos = self.project(12, 6, 0)
            self.render_text("I/O", (io_pos[0]-20, io_pos[1]-110))

            # Render process names
            for key, cube in self.scene.cubes.items():
                if isinstance(cube, Cube) and key in self.scene.active_processes:
                    screen_pos = self.project(cube.position[0], cube.position[1], cube.position[2])
                    self.render_text(cube.name, (screen_pos[0]-20, screen_pos[1]-50))

            # Render metrics
            for i, proc_name in enumerate(self.scene.all_processes):
                runtime_text = f"{proc_name}: VRuntime {self.scene.vRuntimes.get(proc_name, 0):.2f}"
                timeslice_text = f"Time Slice: {self.scene.time_slices.get(proc_name, 0):.2f}s"
                self.render_text(runtime_text, (10, 50 + i*40))
                self.render_text(timeslice_text, (10, 70 + i*40))

            # Draw I/O progress
            self.scene.draw_io_progress(self.render_text, self.display)

            pygame.display.flip()
            clock.tick(60)

    def project(self, x, y, z):
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)
        viewport = glGetIntegerv(GL_VIEWPORT)
        screen_pos = gluProject(x, y, z, modelview, projection, viewport)
        return screen_pos[0], self.display[1] - screen_pos[1]

    def quit(self):
        print("Calling Quit")
        self.running = False
        pygame.quit()

if __name__ == "__main__":
    process_list = ["pro1", "pro2", "pro3", "pro4"]
    niceness = [-10, -5, 0, 5]  # Varying nice values for demonstration
    app = App(process_list, niceness)
    app.run(process_list)
    app.quit()