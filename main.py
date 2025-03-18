import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
from process_handler import Scheduler
from multiprocessing import Manager
import threading

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
            self.angle += 5

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
        process_name = None
        try:
            if not self.notify_queue.empty():
                process_name = self.notify_queue.get_nowait()  # Non-blocking get
        except:
            pass
        
        if process_name and process_name in self.cubes:
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
        self.font = pygame.font.Font(None, 36)
        
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

            for key, cube in self.scene.cubes.items():
                if isinstance(cube, Cube):
                    screen_pos = self.project(cube.position[0], cube.position[1], cube.position[2])
                    self.render_text(cube.name, (screen_pos[0] - 20, screen_pos[1] - 50))

            circle_screen_pos = self.project(self.scene.circle.position[0], self.scene.circle.position[1], self.scene.circle.position[2])
            self.render_text(self.scene.circle.name, (circle_screen_pos[0] - 20, circle_screen_pos[1] - 110))

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
    niceness = [-5, 10, -10]
    app = App(process_list, niceness)
    app.run(process_list)
    app.quit()