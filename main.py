import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
from process_handler import Scheduler

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
        glColor3f(1, 1, 1)  # White color
        for edge in self.edges:
            for vertex in edge:
                glVertex3fv(self.vertices[vertex])
        glEnd()
        glPopMatrix()

    def rotate(self, allowed):
        if allowed:
            self.angle += 1

class Circle:
    def __init__(self, radius=3, num_segments=100, position=(0, 0, 0), name="CPU"):
        self.radius = radius
        self.num_segments = num_segments
        self.position = position
        self.name = name  # Add a name for the circle
    
    def draw(self):
        glPushMatrix()
        glTranslatef(*self.position)
        glBegin(GL_LINE_LOOP)  # Draws only the outline of the circle
        for i in range(self.num_segments):
            theta = 2.0 * math.pi * i / self.num_segments  # Compute the angle
            x = self.radius * math.cos(theta)
            y = self.radius * math.sin(theta)
            glVertex2f(x, y)
        glEnd()
        glPopMatrix()

class Scene:
    def __init__(self,process_list=[]):
        self.cubes = {}
        for i in range(len(process_list)):
            self.cubes[f"{process_list[i]}"] = Cube(position=(i * 4, 0, 0), name=f"{process_list[i]}")
            self.cubes[f"{process_list[i]}_running"] = False

        self.circle = Circle(position=(3, 6, 0), name="CPU")  # Add name to the circle
    
    def draw(self):
        for key, cube in self.cubes.items():
            if isinstance(cube, Cube):  # Only draw actual Cube objects
                cube.draw()
        self.circle.draw()

    def rotation(self, process_name="", rotate=False):
        for key, cube in self.cubes.items():
            if isinstance(cube, Cube):  # Ensure we're only dealing with Cube objects
                cube.position = (int(key[-1]) * 4, 0, 0)  # Reset to original position
                self.cubes[f"{key}_running"] = False  # Stop rotation
            if process_name in self.cubes:
                self.cubes[process_name].position = (3, 6, 0)  # Move to the new position
                self.cubes[process_name].rotate(rotate)

class App:
    def __init__(self,process_list=[],niceness=[]):
        pygame.init()
        self.display = (1200, 600)
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        gluPerspective(45, (self.display[0] / self.display[1]), 0.1, 50.0)
        glTranslatef(-4, -2, -20)  # Move cubes away from camera and center them
        self.scene = Scene(process_list)
        self.running = True

        # Initialize font for text rendering
        self.font = pygame.font.Font(None, 36)  # Default font, size 36

    def render_text(self, text, position):
        """Render text on the screen at (x, y) in 2D coordinates."""
        text_surface = self.font.render(text, True, (255, 255, 255))  # White text
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

    def run(self,process_list=[]):
        process_name = "OS"  # Default process to rotate
        run = False  # Default state

        while self.running:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    self.running = False
                
                # Handle key presses for dynamic input
                for i in range(len(process_list)):
                    if event.type == KEYDOWN:
                        if event.key == K_0:
                            process_name = "OS"

                        if event.key == K_1:
                            process_name = process_list[0]
                        elif event.key == K_2:
                            process_name = process_list[1]
                        elif event.key == K_3:
                            process_name = process_list[2]
                        elif event.key == K_SPACE:
                            run = not run  # Toggle rotation on/off
            
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.scene.draw()
            self.scene.rotation(process_name, run)  # Pass dynamic values

            # Render text labels above the cubes
            for key, cube in self.scene.cubes.items():
                if isinstance(cube, Cube):
                    # Convert 3D position to 2D screen coordinates
                    screen_pos = self.project(cube.position[0], cube.position[1], cube.position[2])
                    self.render_text(cube.name, (screen_pos[0] - 20, screen_pos[1] - 50))  # Adjust text position

            # Render text label for the circle (CPU)
            circle_screen_pos = self.project(self.scene.circle.position[0], self.scene.circle.position[1], self.scene.circle.position[2])
            self.render_text(self.scene.circle.name, (circle_screen_pos[0] - 20, circle_screen_pos[1] - 110))  # Adjust text position

            pygame.display.flip()
            pygame.time.wait(10)  # Control speed

    def project(self, x, y, z):
        """Convert 3D coordinates to 2D screen coordinates."""
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)
        viewport = glGetIntegerv(GL_VIEWPORT)
        screen_pos = gluProject(x, y, z, modelview, projection, viewport)
        return screen_pos[0], self.display[1] - screen_pos[1]  # Invert y for pygame

    def quit(self):
        print("Calling Quit")
        pygame.quit()

if __name__ == "__main__":
    process_list = ["pro1","pro2","pro3"]
    app = App(process_list)
    app.run(process_list)
    app.quit()