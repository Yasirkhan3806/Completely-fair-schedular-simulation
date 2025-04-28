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
                "exe_time": random.randint(0, 10),
                "terminated": False  # Track termination state
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
            self.notify_queue.put({"name": process["name"], "vRuntime": process["vRuntime"], "status": "running"})
            time.sleep(process["time_slice"])

            process["paused_event"].set()
            process["vRuntime"], _ = process["process_obj"].calculate_vRuntime(process["weight"], self.total_weight)
            print(f"Process {process['name']} vRuntime: {process['vRuntime']}")

            if process["vRuntime"] > process["exe_time"] and not process["terminated"]:
                process["process"].terminate()
                process["terminated"] = True  # Mark as terminated
                self.notify_queue.put({"name": process["name"], "status": "terminated"})
                self.process_list.remove(process)
                print(f"Process {process['name']} terminated.")
            else:
                print(f"Process {process['name']} paused.")

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
    def __init__(self, radius=3, num_segments=100, position=(0, 0, 0), name="CPU"):
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
        self.scheduler.add_processes(process_list, weights)
        self.terminated_processes = []  # Track terminated processes
        self.vRuntimes = {proc: 0.0 for proc in process_list}  # Track vRuntime for each process
        
        for i, proc in enumerate(process_list):
            self.cubes[proc] = Cube(position=(i * 4, 0, 0), name=proc)
            self.cubes[f"{proc}_running"] = False
        
        self.circle = Circle(position=(3, 6, 0), name="CPU")

    def draw(self):
        for key, cube in self.cubes.items():
            if isinstance(cube, Cube):
                cube.draw()
        self.circle.draw()

    def update(self):
        # Process all available messages in the queue
        while True:
            try:
                message = self.notify_queue.get_nowait()  # Non-blocking get
                process_name = message["name"]
                status = message["status"]
                
                if status == "running" and process_name in self.cubes:
                    self.vRuntimes[process_name] = message["vRuntime"]  # Update vRuntime
                    for key, cube in self.cubes.items():
                        if isinstance(cube, Cube):
                            if key == process_name:
                                cube.position = (3, 6, 0)  # Move to CPU
                                cube.rotate(True)
                                self.cubes[f"{key}_running"] = True
                            else:
                                cube.position = (int(key[-1]) * 4, 0, 0)  # Reset position
                                cube.rotate(False)
                                self.cubes[f"{key}_running"] = False
                elif status == "terminated" and process_name not in self.terminated_processes:
                    self.terminated_processes.append(process_name)
                    print(f"Termination message processed for {process_name}")
            except:
                break  # Exit loop when queue is empty

class App:
    def __init__(self, process_list, niceness):
        pygame.init()
        self.display = (1200, 600)
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        gluPerspective(45, (self.display[0] / self.display[1]), 0.1, 50.0)
        glTranslatef(-4, -2, -20)
        
        self.manager = Manager()
        self.notify_queue = self.manager.Queue()  # Shared queue
        self.scene = Scene(process_list, niceness, self.notify_queue)
        self.running = True
        self.font = pygame.font.Font(None, 24)  # Smaller font size
        
        # Start scheduler in a separate thread
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

            self.scene.update()  # Update based on notify_queue

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.scene.draw()

            # Render process names above cubes
            for key, cube in self.scene.cubes.items():
                if isinstance(cube, Cube):
                    screen_pos = self.project(cube.position[0], cube.position[1], cube.position[2])
                    self.render_text(cube.name, (screen_pos[0] - 20, screen_pos[1] - 50))

            # Render CPU label
            circle_screen_pos = self.project(self.scene.circle.position[0], self.scene.circle.position[1], self.scene.circle.position[2])
            self.render_text(self.scene.circle.name, (circle_screen_pos[0] - 20, circle_screen_pos[1] - 110))

            # Render static virtual runtime for each process on the left
            for i, proc_name in enumerate(process_list):
                runtime_text = f"The virtual Runtime of the process '{proc_name}' is {self.scene.vRuntimes[proc_name]:.2f}"
                self.render_text(runtime_text, (10, 50 + i * 30))

            # Render terminated processes on the right
            for i, proc_name in enumerate(self.scene.terminated_processes):
                term_text = f"The process '{proc_name}' is terminated"
                self.render_text(term_text, (self.display[0] - 250, 50 + i * 30))

            pygame.display.flip()
            clock.tick(60)  # 60 FPS

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
    process_list = ["pro1", "pro2", "pro3"]
    niceness = [-10, -10, -10]
    app = App(process_list, niceness)
    app.run(process_list)
    app.quit()