import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math

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

    def __init__(self, position=(0, 0, 0)):
        self.position = position
        self.angle = 0
    
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
    def __init__(self, radius=3, num_segments=100, position=(0, 0, 0)):
        self.radius = radius
        self.num_segments = num_segments
        self.position = position
    
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
    def __init__(self):
        self.cubes = {}
        for i in range(3):
            self.cubes[f"p{i}"] = Cube(position=(i * 4, 0, 0))
            self.cubes[f"p{i}_running"] = False

        self.circle = Circle(position=(3, 6, 0))
    
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
    def __init__(self):
        pygame.init()
        self.display = (1200, 600)
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        gluPerspective(45, (self.display[0] / self.display[1]), 0.1, 50.0)
        glTranslatef(-4, -2, -20)  # Move cubes away from camera and center them
        self.scene = Scene()
        self.running = True

        # Initialize font for text rendering
        self.font = pygame.font.Font(None, 36)  # Default font, size 36

    def render_text(self, text, x, y):
        """Render text on the screen at (x, y) in 2D coordinates."""
        text_surface = self.font.render(text, True, (255, 255, 255))  # White text
        text_data = pygame.image.tostring(text_surface, "RGBA", True)

        glPushMatrix()
        glLoadIdentity()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.display[0], self.display[1], 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glRasterPos2f(x, y)
        glDrawPixels(text_surface.get_width(), text_surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)

        glDisable(GL_BLEND)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def run(self):
        process_name = "p0"  # Default process to rotate
        run = False  # Default state

        while self.running:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    self.running = False
                
                # Handle key presses for dynamic input
                if event.type == KEYDOWN:
                    if event.key == K_1:
                        process_name = "p0"
                    elif event.key == K_2:
                        process_name = "p1"
                    elif event.key == K_3:
                        process_name = "p2"
                    elif event.key == K_SPACE:
                        run = not run  # Toggle rotation on/off
            
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.scene.draw()
            self.scene.rotation(process_name, run)  # Pass dynamic values

            # Render text labels
            self.render_text("Cube 0", 100, 50)  # Label for Cube 0
            self.render_text("Cube 1", 500, 50)  # Label for Cube 1
            self.render_text("Cube 2", 900, 50)  # Label for Cube 2
            self.render_text("Circle", 550, 300)  # Label for Circle

            pygame.display.flip()
            pygame.time.wait(10)  # Control speed

    def quit(self):
        print("Calling Quit")
        pygame.quit()

if __name__ == "__main__":
    app = App()
    app.run()
    app.quit()