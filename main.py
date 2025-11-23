import math
import random
from dataclasses import dataclass
from typing import List, Tuple

import pygame
from pygame.locals import (
    DOUBLEBUF,
    OPENGL,
    QUIT,
    VIDEORESIZE,
    KEYDOWN,
    K_ESCAPE,
    K_SPACE,
    K_LSHIFT,
    K_RSHIFT,
    K_w,
    K_a,
    K_s,
    K_d,
    K_UP,
    K_DOWN,
    K_LEFT,
    K_RIGHT,
    MOUSEBUTTONDOWN,
)
from OpenGL.GL import (
    glBegin,
    glBindTexture,
    glBlendFunc,
    glCallList,
    glClear,
    glClearColor,
    glColor3f,
    glColor4f,
    glDeleteTextures,
    glDisable,
    glEnable,
    glEnd,
    glEndList,
    glGenLists,
    glGenTextures,
    glLoadIdentity,
    glLineWidth,
    glMatrixMode,
    glNewList,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glTranslatef,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glVertex3f,
    glViewport,
    GL_COLOR_BUFFER_BIT,
    GL_COMPILE,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_MODELVIEW,
    GL_PROJECTION,
    GL_QUADS,
    GL_BLEND,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    GL_RGBA,
    GL_LINEAR,
    GL_TEXTURE_2D,
    GL_CLAMP_TO_EDGE,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
)
from OpenGL.GLU import gluPerspective


WINDOW_SIZE: Tuple[int, int] = (1280, 720)
FOV = 75
MOVEMENT_SPEED = 6.4
TURN_SPEED = 260.0
PITCH_SPEED = 160.0
MOUSE_SENSITIVITY = 0.14
JUMP_VELOCITY = 6.5
GRAVITY = 18.0
PLAYER_HEIGHT = 1.8
GROUND_LEVEL = 0.0
PLATFORM_RADIUS = 58
BOUNDS_RADIUS = PLATFORM_RADIUS - 0.6
PLAYER_COLLISION_RADIUS = 0.35
PUNCH_RANGE = 3.2
CONTACT_RANGE = 1.1
MAX_HEALTH = 100.0
HEALTH_REGEN_PER_SECOND = 2.2
HEALTH_DAMAGE_PER_SECOND = 60.0
ZOMBIE_RESPAWN_INTERVAL = 2.6
BASE_TARGET_ZOMBIE_COUNT = 6
ROOF_HEIGHT = 12.0
BOOST_MULTIPLIER = 3.0
BOOST_DURATION = 10.0
BOOST_COOLDOWN = 30.0

LOOK_MODE_ARROWS = "arrows"
LOOK_MODE_MOUSE = "mouse"


@dataclass
class Player:
    position: pygame.math.Vector3
    velocity: pygame.math.Vector3
    yaw: float = 0.0
    pitch: float = 0.0
    health: float = MAX_HEALTH

    def apply_gravity(self, dt: float) -> None:
        if self.position.y > PLAYER_HEIGHT or self.velocity.y > 0:
            self.velocity.y -= GRAVITY * dt

    def move_horizontal(
        self,
        forward: float,
        strafe: float,
        dt: float,
        colliders: List[Tuple[float, float, float]],
        movement_speed: float = MOVEMENT_SPEED,
    ) -> None:
        radians_yaw = math.radians(self.yaw)
        forward_vec = pygame.math.Vector3(
            math.sin(radians_yaw), 0, math.cos(radians_yaw)
        )
        right_vec = pygame.math.Vector3(forward_vec.z, 0, -forward_vec.x)
        direction = forward_vec * forward + right_vec * strafe
        if direction.length_squared() > 0:
            direction = direction.normalize()
            previous = self.position.copy()
            self.position += direction * movement_speed * dt
            resolve_tree_collisions(self.position, previous, colliders)

    def integrate(self, dt: float) -> None:
        self.position += self.velocity * dt
        if self.position.y < PLAYER_HEIGHT:
            self.position.y = PLAYER_HEIGHT
            self.velocity.y = 0

    def jump(self) -> None:
        if self.position.y <= PLAYER_HEIGHT + 1e-3:
            self.velocity.y = JUMP_VELOCITY


@dataclass
class Zombie:
    position: pygame.math.Vector3
    speed: float
    size: float

    def chase(self, target: pygame.math.Vector3, dt: float) -> None:
        direction = target - self.position
        direction.y = 0
        if direction.length_squared() > 1e-6:
            direction = direction.normalize()
            self.position += direction * self.speed * dt


@dataclass
class Tree:
    x: int
    z: int
    trunk_height: int
    crown_size: int


class Renderer:
    def __init__(self, window_size: Tuple[int, int]):
        self.window_size = window_size
        self._init_pygame()
        self._init_opengl()
        self.title_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.hud_font = pygame.font.SysFont("Arial", 28, bold=True)
        self.trees = self._generate_trees()
        self.tree_colliders = self._build_tree_colliders()
        self.platform_list = self._build_platform_list()
        self.tree_list = self._build_tree_list()

    def _init_pygame(self) -> None:
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode(self.window_size, DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Smooth Crafty First-Person Demo")

    def _init_opengl(self) -> None:
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.45, 0.7, 1.0, 1.0)
        self._resize(*self.window_size)

    def _generate_trees(self) -> List[Tree]:
        random.seed(8)
        trees: List[Tree] = []
        attempts = 0
        desired = 80
        occupied: set[Tuple[int, int]] = set()
        while len(trees) < desired and attempts < desired * 20:
            attempts += 1
            gx = random.randint(-PLATFORM_RADIUS + 2, PLATFORM_RADIUS - 2)
            gz = random.randint(-PLATFORM_RADIUS + 2, PLATFORM_RADIUS - 2)
            if abs(gx) < 4 and abs(gz) < 4:
                continue
            if any((gx + dx, gz + dz) in occupied for dx in range(-2, 3) for dz in range(-2, 3)):
                continue
            occupied.add((gx, gz))
            trunk_height = random.randint(2, 4)
            crown_size = random.randint(2, 3)
            trees.append(Tree(gx, gz, trunk_height, crown_size))
        return trees

    def _build_tree_colliders(self) -> List[Tuple[float, float, float]]:
        colliders: List[Tuple[float, float, float]] = []
        for tree in self.trees:
            colliders.append((float(tree.x), float(tree.z), 0.65))
        return colliders

    def _resize(self, width: int, height: int) -> None:
        self._apply_projection(FOV, width, height)

    def clear(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    def present(self) -> None:
        pygame.display.flip()

    def set_camera(self, player: Player) -> None:
        glLoadIdentity()
        yaw, pitch = player.yaw, player.pitch
        glRotatef(-pitch, 1, 0, 0)
        glRotatef(-yaw, 0, 1, 0)
        glTranslatef(-player.position.x, -player.position.y, -player.position.z)

    def draw_cube(self, x: float, y: float, z: float, size: float, color: Tuple[float, float, float]) -> None:
        half = size / 2.0
        glColor3f(*color)
        glBegin(GL_QUADS)
        # Top
        glVertex3f(x - half, y + half, z - half)
        glVertex3f(x + half, y + half, z - half)
        glVertex3f(x + half, y + half, z + half)
        glVertex3f(x - half, y + half, z + half)
        # Bottom
        glVertex3f(x - half, y - half, z + half)
        glVertex3f(x + half, y - half, z + half)
        glVertex3f(x + half, y - half, z - half)
        glVertex3f(x - half, y - half, z - half)
        # Front
        glVertex3f(x - half, y - half, z + half)
        glVertex3f(x - half, y + half, z + half)
        glVertex3f(x + half, y + half, z + half)
        glVertex3f(x + half, y - half, z + half)
        # Back
        glVertex3f(x + half, y - half, z - half)
        glVertex3f(x + half, y + half, z - half)
        glVertex3f(x - half, y + half, z - half)
        glVertex3f(x - half, y - half, z - half)
        # Left
        glVertex3f(x - half, y - half, z - half)
        glVertex3f(x - half, y + half, z - half)
        glVertex3f(x - half, y + half, z + half)
        glVertex3f(x - half, y - half, z + half)
        # Right
        glVertex3f(x + half, y - half, z + half)
        glVertex3f(x + half, y + half, z + half)
        glVertex3f(x + half, y + half, z - half)
        glVertex3f(x + half, y - half, z - half)
        glEnd()

    def draw_platform(self) -> None:
        glCallList(self.platform_list)

    def draw_trees(self) -> None:
        glCallList(self.tree_list)

    def draw_world(self) -> None:
        self.draw_platform()
        self.draw_trees()

    def _apply_projection(self, fov: float, width: int, height: int) -> None:
        aspect_ratio = width / float(height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(fov, aspect_ratio, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def draw_arena_shell(self) -> None:
        roof_extent = PLATFORM_RADIUS + 2
        roof_y = ROOF_HEIGHT
        glColor4f(0.7, 0.7, 0.7, 0.2)
        glBegin(GL_QUADS)
        glVertex3f(-roof_extent, roof_y, -roof_extent)
        glVertex3f(roof_extent, roof_y, -roof_extent)
        glVertex3f(roof_extent, roof_y, roof_extent)
        glVertex3f(-roof_extent, roof_y, roof_extent)
        glEnd()

        wall_color = (0.5, 0.5, 0.5, 1.0)
        glColor4f(*wall_color)
        glBegin(GL_QUADS)
        # North wall
        glVertex3f(-roof_extent, 0, -roof_extent)
        glVertex3f(roof_extent, 0, -roof_extent)
        glVertex3f(roof_extent, roof_y, -roof_extent)
        glVertex3f(-roof_extent, roof_y, -roof_extent)
        # South wall
        glVertex3f(-roof_extent, 0, roof_extent)
        glVertex3f(roof_extent, 0, roof_extent)
        glVertex3f(roof_extent, roof_y, roof_extent)
        glVertex3f(-roof_extent, roof_y, roof_extent)
        # West wall
        glVertex3f(-roof_extent, 0, -roof_extent)
        glVertex3f(-roof_extent, 0, roof_extent)
        glVertex3f(-roof_extent, roof_y, roof_extent)
        glVertex3f(-roof_extent, roof_y, -roof_extent)
        # East wall
        glVertex3f(roof_extent, 0, -roof_extent)
        glVertex3f(roof_extent, 0, roof_extent)
        glVertex3f(roof_extent, roof_y, roof_extent)
        glVertex3f(roof_extent, roof_y, -roof_extent)
        glEnd()

    def _build_platform_list(self) -> int:
        list_id = glGenLists(1)
        glNewList(list_id, GL_COMPILE)
        for gx in range(-PLATFORM_RADIUS, PLATFORM_RADIUS + 1):
            for gz in range(-PLATFORM_RADIUS, PLATFORM_RADIUS + 1):
                shade = 0.6 if (gx + gz) % 2 == 0 else 0.5
                self.draw_cube(gx, GROUND_LEVEL - 0.5, gz, 1.0, (0.35, shade, 0.35))
        glEndList()
        return list_id

    def _build_tree_list(self) -> int:
        list_id = glGenLists(1)
        glNewList(list_id, GL_COMPILE)
        for tree in self.trees:
            for y in range(tree.trunk_height):
                self.draw_cube(
                    tree.x,
                    GROUND_LEVEL + y + 0.5,
                    tree.z,
                    1.0,
                    (0.45, 0.3, 0.2),
                )

            crown_base = GROUND_LEVEL + tree.trunk_height + 0.5
            for y in range(tree.crown_size):
                layer = crown_base + y
                leaves = [
                    (tree.x, layer, tree.z),
                    (tree.x + 1, layer, tree.z),
                    (tree.x - 1, layer, tree.z),
                    (tree.x, layer, tree.z + 1),
                    (tree.x, layer, tree.z - 1),
                ]
                for lx, ly, lz in leaves:
                    self.draw_cube(lx, ly, lz, 1.0, (0.1, 0.55, 0.15))
        glEndList()
        return list_id

    def draw_zombie(self, zombie: "Zombie", highlight: bool) -> None:
        base = zombie.position
        leg_height = zombie.size
        body_height = zombie.size
        head_height = zombie.size * 0.8
        base_color = (0.5, 0.12, 0.12) if not highlight else (0.78, 0.32, 0.32)
        mid_color = (0.65, 0.12, 0.12) if not highlight else (0.9, 0.36, 0.36)
        head_color = (0.75, 0.16, 0.16) if not highlight else (1.0, 0.42, 0.42)
        self.draw_cube(base.x, base.y + leg_height / 2.0, base.z, zombie.size, base_color)
        self.draw_cube(
            base.x,
            base.y + leg_height + body_height / 2.0,
            base.z,
            zombie.size,
            mid_color,
        )
        self.draw_cube(
            base.x,
            base.y + leg_height + body_height + head_height / 2.0,
            base.z,
            head_height,
            head_color,
        )

    def draw_health_bar(self, health_ratio: float) -> None:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.window_size[0], self.window_size[1], 0, -1, 1)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)

        bar_width = self.window_size[0] * 0.4
        bar_height = 18
        margin = 24
        x0 = (self.window_size[0] - bar_width) / 2
        y0 = self.window_size[1] - margin - bar_height
        x1 = x0 + bar_width
        y1 = y0 + bar_height

        glColor3f(0.1, 0.1, 0.1)
        glBegin(GL_QUADS)
        glVertex3f(x0, y0, 0)
        glVertex3f(x1, y0, 0)
        glVertex3f(x1, y1, 0)
        glVertex3f(x0, y1, 0)
        glEnd()

        filled_width = bar_width * clamp(health_ratio, 0.0, 1.0)
        inner_width = max(0.0, filled_width - 4)
        glColor3f(0.78, 0.18, 0.18)
        glBegin(GL_QUADS)
        glVertex3f(x0 + 2, y0 + 2, 0)
        glVertex3f(x0 + 2 + inner_width, y0 + 2, 0)
        glVertex3f(x0 + 2 + inner_width, y1 - 2, 0)
        glVertex3f(x0 + 2, y1 - 2, 0)
        glEnd()

        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def draw_button(
        self,
        rect: pygame.Rect,
        fill_color: Tuple[float, float, float],
        border_color: Tuple[float, float, float],
        label: str,
        hover: bool,
    ) -> None:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.window_size[0], self.window_size[1], 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)

        shade = 0.06 if hover else 0.0
        glColor3f(fill_color[0] + shade, fill_color[1] + shade, fill_color[2] + shade)
        glBegin(GL_QUADS)
        glVertex3f(rect.left, rect.top, 0)
        glVertex3f(rect.right, rect.top, 0)
        glVertex3f(rect.right, rect.bottom, 0)
        glVertex3f(rect.left, rect.bottom, 0)
        glEnd()

        glColor3f(*border_color)
        glLineWidth(3)
        glBegin(GL_QUADS)
        glVertex3f(rect.left, rect.top, 0)
        glVertex3f(rect.right, rect.top, 0)
        glVertex3f(rect.right, rect.top + 3, 0)
        glVertex3f(rect.left, rect.top + 3, 0)
        glVertex3f(rect.left, rect.bottom - 3, 0)
        glVertex3f(rect.right, rect.bottom - 3, 0)
        glVertex3f(rect.right, rect.bottom, 0)
        glVertex3f(rect.left, rect.bottom, 0)
        glVertex3f(rect.left, rect.top, 0)
        glVertex3f(rect.left + 3, rect.top, 0)
        glVertex3f(rect.left + 3, rect.bottom, 0)
        glVertex3f(rect.left, rect.bottom, 0)
        glVertex3f(rect.right - 3, rect.top, 0)
        glVertex3f(rect.right, rect.top, 0)
        glVertex3f(rect.right, rect.bottom, 0)
        glVertex3f(rect.right - 3, rect.bottom, 0)
        glEnd()

        self._draw_text_surface(
            self.hud_font.render(label, True, (255, 255, 255)),
            rect.centerx - self.hud_font.size(label)[0] / 2,
            rect.centery - self.hud_font.get_height() / 2,
        )

        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def _draw_text_surface(self, surface: pygame.Surface, x: float, y: float) -> None:
        text_data = pygame.image.tostring(surface, "RGBA", True)
        width, height = surface.get_size()

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.window_size[0], self.window_size[1], 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            text_data,
        )

        x1 = x + width
        y1 = y + height

        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1)
        glVertex3f(x, y, 0)
        glTexCoord2f(1, 1)
        glVertex3f(x1, y, 0)
        glTexCoord2f(1, 0)
        glVertex3f(x1, y1, 0)
        glTexCoord2f(0, 0)
        glVertex3f(x, y1, 0)
        glEnd()

        glDeleteTextures([tex_id])
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def draw_text(self, text: str, y: float, color: Tuple[float, float, float]) -> None:
        surface = self.title_font.render(
            text, True, (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        x = (self.window_size[0] - surface.get_width()) / 2
        self._draw_text_surface(surface, x, y)

    def draw_text_at(
        self, text: str, x: float, y: float, color: Tuple[float, float, float], use_title: bool = False
    ) -> None:
        font = self.title_font if use_title else self.hud_font
        surface = font.render(
            text, True, (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        self._draw_text_surface(surface, x, y)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def clamp_to_platform(position: pygame.math.Vector3) -> None:
    position.x = clamp(position.x, -BOUNDS_RADIUS, BOUNDS_RADIUS)
    position.z = clamp(position.z, -BOUNDS_RADIUS, BOUNDS_RADIUS)


def resolve_tree_collisions(
    position: pygame.math.Vector3,
    previous_position: pygame.math.Vector3,
    colliders: List[Tuple[float, float, float]],
) -> None:
    for cx, cz, radius in colliders:
        dx = position.x - cx
        dz = position.z - cz
        min_dist = radius + PLAYER_COLLISION_RADIUS
        if dx * dx + dz * dz < min_dist * min_dist:
            # First try reverting X, then Z if still colliding to keep motion smooth
            position.x = previous_position.x
            dx = position.x - cx
            dz = position.z - cz
            if dx * dx + dz * dz < min_dist * min_dist:
                position.z = previous_position.z
                dx = position.x - cx
                dz = position.z - cz
                if dx * dx + dz * dz < min_dist * min_dist:
                    position.x = previous_position.x
                    position.z = previous_position.z


def handle_window_resize(renderer: Renderer, event: pygame.event.Event) -> None:
    width, height = event.size
    renderer.window_size = (width, height)
    renderer._resize(width, height)


def choose_look_mode(renderer: Renderer) -> str | None:
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)
    pygame.mouse.get_rel()
    button_width = 320
    button_height = 90
    spacing = 40
    center_x = renderer.window_size[0] // 2
    center_y = renderer.window_size[1] // 2
    arrow_rect = pygame.Rect(
        center_x - button_width - spacing // 2,
        center_y - button_height // 2,
        button_width,
        button_height,
    )
    mouse_rect = pygame.Rect(
        center_x + spacing // 2,
        center_y - button_height // 2,
        button_width,
        button_height,
    )

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                return None
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                return None
            if event.type == MOUSEBUTTONDOWN and event.button == 1:
                pos = pygame.mouse.get_pos()
                if arrow_rect.collidepoint(pos):
                    return LOOK_MODE_ARROWS
                if mouse_rect.collidepoint(pos):
                    return LOOK_MODE_MOUSE

        pos = pygame.mouse.get_pos()
        arrow_hover = arrow_rect.collidepoint(pos)
        mouse_hover = mouse_rect.collidepoint(pos)

        renderer.clear()
        renderer.draw_text_at("Choose look mode", center_x - 190, center_y - 180, (1.0, 1.0, 1.0), use_title=True)
        renderer.draw_button(arrow_rect, (0.18, 0.35, 0.62), (0.1, 0.18, 0.32), "Look using arrows", arrow_hover)
        renderer.draw_button(mouse_rect, (0.18, 0.35, 0.62), (0.1, 0.18, 0.32), "Look using mouse", mouse_hover)
        renderer.present()


def handle_input(
    player: Player,
    dt: float,
    tree_colliders: List[Tuple[float, float, float]],
    keys: pygame.key.ScancodeWrapper,
    look_mode: str,
    mouse_delta: Tuple[float, float],
    movement_speed: float,
) -> bool:
    forward = 0.0
    strafe = 0.0
    if keys[K_w]:
        forward -= 1.0
    if keys[K_s]:
        forward += 1.0
    if keys[K_d]:
        strafe += 1.0
    if keys[K_a]:
        strafe -= 1.0

    player.move_horizontal(forward, strafe, dt, tree_colliders, movement_speed)
    moved = abs(forward) + abs(strafe) > 0

    yaw_delta = 0.0
    pitch_delta = 0.0
    if look_mode == LOOK_MODE_ARROWS:
        if keys[K_LEFT]:
            yaw_delta -= 1.0
        if keys[K_RIGHT]:
            yaw_delta += 1.0
        if keys[K_UP]:
            pitch_delta += 1.0
        if keys[K_DOWN]:
            pitch_delta -= 1.0
        player.yaw = (player.yaw - yaw_delta * TURN_SPEED * dt) % 360
        player.pitch = clamp(player.pitch + pitch_delta * PITCH_SPEED * dt, -80, 80)
    else:
        dx, dy = mouse_delta
        player.yaw = (player.yaw - dx * MOUSE_SENSITIVITY) % 360
        player.pitch = clamp(player.pitch - dy * MOUSE_SENSITIVITY, -80, 80)

    if keys[K_SPACE]:
        player.jump()

    return moved


def spawn_zombies(
    count: int,
    colliders: List[Tuple[float, float, float]] | None = None,
    existing_speeds: List[float] | None = None,
    speed_scale: float = 1.0,
) -> List[Zombie]:
    zombies: List[Zombie] = []
    used_speeds = set(existing_speeds or [])
    for _ in range(count):
        pos = pygame.math.Vector3()
        attempts = 0
        while attempts < 40:
            attempts += 1
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(BOUNDS_RADIUS * 0.35, BOUNDS_RADIUS - 2.0)
            pos = pygame.math.Vector3(
                math.cos(angle) * distance,
                GROUND_LEVEL + 0.5,
                math.sin(angle) * distance,
            )
            if colliders:
                too_close = False
                for cx, cz, radius in colliders:
                    dx = pos.x - cx
                    dz = pos.z - cz
                    if dx * dx + dz * dz < (radius + 0.6) ** 2:
                        too_close = True
                        break
                if too_close:
                    continue
            break
        size = random.uniform(0.9, 1.35)
        base_speed = MOVEMENT_SPEED * random.uniform(0.92, 1.08) * speed_scale
        speed = base_speed
        tries = 0
        while any(abs(speed - seen) < 0.02 for seen in used_speeds) and tries < 20:
            speed = MOVEMENT_SPEED * random.uniform(0.92, 1.08) * speed_scale
            tries += 1
        used_speeds.add(speed)
        zombies.append(Zombie(position=pos, speed=speed, size=size))
    return zombies


def update_zombies(zombies: List[Zombie], player: Player, dt: float) -> None:
    for zombie in zombies:
        zombie.chase(player.position, dt)
        zombie.position.y = GROUND_LEVEL + zombie.size / 2.0
        clamp_to_platform(zombie.position)


def punch_zombies(zombies: List[Zombie], player: Player) -> None:
    closest_index = -1
    closest_distance = float("inf")
    for idx, zombie in enumerate(zombies):
        offset = zombie.position - player.position
        offset.y = 0
        distance = offset.length()
        if distance <= PUNCH_RANGE + zombie.size * 0.5 and distance < closest_distance:
            closest_distance = distance
            closest_index = idx
    if closest_index >= 0:
        zombies.pop(closest_index)


def update_health(player: Player, zombies: List[Zombie], dt: float, moved: bool) -> None:
    if not moved and player.health < MAX_HEALTH:
        player.health = min(MAX_HEALTH, player.health + HEALTH_REGEN_PER_SECOND * dt)

    for zombie in zombies:
        offset = zombie.position - player.position
        offset.y = 0
        if offset.length() <= CONTACT_RANGE + zombie.size * 0.5:
            player.health -= HEALTH_DAMAGE_PER_SECOND * dt

    player.health = clamp(player.health, 0.0, MAX_HEALTH)


def main() -> None:
    renderer = Renderer(WINDOW_SIZE)
    look_mode = choose_look_mode(renderer)
    if look_mode is None:
        pygame.quit()
        return

    using_mouse_look = look_mode == LOOK_MODE_MOUSE
    pygame.mouse.set_visible(not using_mouse_look)
    pygame.event.set_grab(using_mouse_look)
    pygame.mouse.get_rel()

    player = Player(position=pygame.math.Vector3(0.0, PLAYER_HEIGHT, 6.0), velocity=pygame.math.Vector3())
    zombies = spawn_zombies(8, renderer.tree_colliders)
    clock = pygame.time.Clock()
    spawn_timer = 0.0
    survival_time = 0.0
    game_over = False
    death_time = 0.0
    boost_cooldown = 0.0
    boost_active = 0.0

    running = True
    while running:
        dt = min(clock.tick(90) / 1000.0, 1 / 45)
        mouse_click = False
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == VIDEORESIZE:
                handle_window_resize(renderer, event)
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
            elif not game_over and event.type == KEYDOWN and event.key in (K_LSHIFT, K_RSHIFT):
                if boost_cooldown <= 0.0 and boost_active <= 0.0:
                    boost_active = BOOST_DURATION
                    boost_cooldown = BOOST_COOLDOWN
            elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True

        if not game_over:
            keys = pygame.key.get_pressed()
            if using_mouse_look:
                mouse_delta = pygame.mouse.get_rel()
            else:
                pygame.mouse.get_rel()
                mouse_delta = (0.0, 0.0)

            if boost_cooldown > 0.0:
                boost_cooldown = max(0.0, boost_cooldown - dt)
            if boost_active > 0.0:
                boost_active = max(0.0, boost_active - dt)

            speed_multiplier = BOOST_MULTIPLIER if boost_active > 0.0 else 1.0
            moved = handle_input(
                player,
                dt,
                renderer.tree_colliders,
                keys,
                look_mode,
                mouse_delta,
                MOVEMENT_SPEED * speed_multiplier,
            )
            player.apply_gravity(dt)
            player.integrate(dt)
            clamp_to_platform(player.position)
            update_zombies(zombies, player, dt)
            update_health(player, zombies, dt, moved)

            survival_time += dt
            spawn_timer += dt
            target_count = min(30, BASE_TARGET_ZOMBIE_COUNT + int(survival_time // 20) * 2)
            speed_scale = 1.0 + min(0.9, survival_time * 0.01)
            spawn_interval = max(1.2, ZOMBIE_RESPAWN_INTERVAL - survival_time * 0.008)
            if spawn_timer >= spawn_interval and len(zombies) < target_count:
                slots = target_count - len(zombies)
                spawn_count = min(2 + target_count // 8, slots)
                zombies.extend(
                    spawn_zombies(spawn_count, renderer.tree_colliders, [z.speed for z in zombies], speed_scale)
                )
                spawn_timer = 0.0

            if mouse_click:
                punch_zombies(zombies, player)

            if player.health <= 0.0:
                game_over = True
                death_time = survival_time
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)
        else:
            pygame.mouse.set_visible(True)

        renderer.clear()
        renderer.set_camera(player)
        renderer.draw_world()
        renderer.draw_arena_shell()
        for zombie in zombies:
            offset = zombie.position - player.position
            offset.y = 0
            in_range = offset.length() <= PUNCH_RANGE + zombie.size * 0.5
            renderer.draw_zombie(zombie, in_range)

        renderer.draw_health_bar(player.health / MAX_HEALTH)
        timer_text = f"Time: {int(survival_time // 60):02d}:{int(survival_time % 60):02d}"
        renderer.draw_text_at(timer_text, 18, renderer.window_size[1] - 64, (1.0, 1.0, 1.0))
        if boost_active > 0.0:
            boost_text = f"Boost: {boost_active:04.1f}s" if boost_active > 0.0 else "Boost: --"
            renderer.draw_text_at(boost_text, 18, 18, (0.6, 1.0, 0.8))
        elif boost_cooldown > 0.0:
            renderer.draw_text_at(f"Boost in: {boost_cooldown:04.1f}s", 18, 18, (1.0, 0.9, 0.4))
        else:
            renderer.draw_text_at("Boost: Ready", 18, 18, (0.6, 1.0, 0.8))
        if player.pitch > 55:
            renderer.draw_text("HUNGER GAMES", 20, (1.0, 0.86, 0.18))

        if game_over:
            renderer.draw_text_at("U DIED", renderer.window_size[0] * 0.5 - 110, renderer.window_size[1] * 0.42, (1.0, 0.2, 0.2), use_title=True)
            renderer.draw_text_at(
                f"Survived: {int(death_time // 60):02d}:{int(death_time % 60):02d}",
                renderer.window_size[0] * 0.5 - 160,
                renderer.window_size[1] * 0.42 + 54,
                (1.0, 0.9, 0.9),
            )

        renderer.present()

    pygame.quit()


if __name__ == "__main__":
    main()
