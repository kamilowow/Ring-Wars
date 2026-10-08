import pygame
import random
import math
import sys

# ============================================================
# BOXING GAME - PYGAME
# Sin imágenes externas: todo se dibuja con Pygame.
# ============================================================

pygame.init()

# ---------------- CONFIGURACIÓN ----------------
WIDTH, HEIGHT = 1000, 600
FPS = 60

SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("RING WARS - 2D Boxing")
CLOCK = pygame.time.Clock()

# Colores
WHITE = (245, 245, 245)
BLACK = (10, 10, 14)
DARK = (22, 22, 30)
GRAY = (75, 75, 85)
LIGHT_GRAY = (145, 145, 155)
RED = (220, 55, 55)
DARK_RED = (120, 25, 30)
GREEN = (55, 205, 90)
YELLOW = (245, 205, 55)
BLUE = (55, 110, 225)
CYAN = (60, 210, 220)
SKIN = (235, 175, 130)
SKIN_DARK = (190, 125, 90)
ROPE = (185, 35, 45)
MAT = (48, 48, 58)

FLOOR_Y = 475
RING_LEFT = 80
RING_RIGHT = WIDTH - 80

FONT = pygame.font.SysFont("arial", 22, bold=True)
SMALL = pygame.font.SysFont("arial", 17, bold=True)
BIG = pygame.font.SysFont("arial", 42, bold=True)
HUGE = pygame.font.SysFont("arial", 76, bold=True)


def clamp(value, low, high):
    return max(low, min(high, value))


# ============================================================
# FIGHTER
# ============================================================

class Fighter:
    def __init__(self, x, name, is_ai, facing_left, body_color, glove_color):
        self.start_x = x
        self.x = float(x)
        self.y = FLOOR_Y

        self.name = name
        self.is_ai = is_ai
        self.facing_left = facing_left

        self.body_color = body_color
        self.glove_color = glove_color

        self.max_health = 100.0
        self.health = 100.0
        self.max_stamina = 100.0
        self.stamina = 100.0

        self.speed = 4.0
        self.state = "idle"
        self.attack = None
        self.attack_frame = 0
        self.attack_duration = 0
        self.has_hit = False

        self.block_timer = 0
        self.stun_timer = 0
        self.flash_timer = 0

        self.ai_timer = 0
        self.ai_block_timer = 0

        self.score = 0

        # Duración, daño, coste, alcance, ventana de impacto
        self.attacks = {
            "jab": {
                "duration": 20,
                "damage": 5,
                "stamina": 8,
                "reach": 52,
                "impact": 9
            },
            "cross": {
                "duration": 30,
                "damage": 12,
                "stamina": 17,
                "reach": 78,
                "impact": 14
            },
            "hook": {
                "duration": 34,
                "damage": 16,
                "stamina": 21,
                "reach": 62,
                "impact": 16
            }
        }

    # ---------- GEOMETRÍA ----------
    def body_rect(self):
        return pygame.Rect(int(self.x - 25), int(self.y - 120), 50, 120)

    def hurtbox(self):
        # Cabeza + torso. Esto hace que pegarle al guante no cuente como daño.
        body = self.body_rect()
        return pygame.Rect(body.x + 5, body.y + 5, 40, 105)

    def attack_rect(self):
        if self.attack not in self.attacks:
            return pygame.Rect(0, 0, 0, 0)

        data = self.attacks[self.attack]
        progress = self.attack_frame / max(1, data["duration"])

        # El brazo sale y vuelve.
        extension = math.sin(progress * math.pi)

        direction = -1 if self.facing_left else 1
        base_x = self.x + direction * 20
        glove_x = base_x + direction * extension * data["reach"]

        # Hook tiene un movimiento ligeramente circular.
        glove_y = self.y - 91
        if self.attack == "hook":
            glove_y -= math.sin(progress * math.pi) * 13

        return pygame.Rect(int(glove_x - 11), int(glove_y - 11), 22, 22)

    # ---------- ACCIONES ----------
    def can_act(self):
        return (
            self.health > 0
            and self.stun_timer <= 0
            and self.state not in ("attack", "ko")
        )

    def start_attack(self, attack_name):
        if not self.can_act():
            return False

        if attack_name not in self.attacks:
            return False

        data = self.attacks[attack_name]

        if self.stamina < data["stamina"]:
            return False

        self.stamina -= data["stamina"]
        self.attack = attack_name
        self.attack_frame = 0
        self.attack_duration = data["duration"]
        self.has_hit = False
        self.state = "attack"
        self.block_timer = 0
        return True

    def start_block(self):
        if self.health <= 0 or self.stun_timer > 0 or self.state == "attack":
            return False

        self.state = "block"
        return True

    def stop_block(self):
        if self.state == "block":
            self.state = "idle"

    def move(self, amount):
        if not self.can_act():
            return

        self.state = "move"
        self.x += amount
        self.x = clamp(self.x, RING_LEFT + 25, RING_RIGHT - 25)

    # ---------- DAÑO ----------
    def receive_hit(self, damage, attack_name):
        self.flash_timer = 5

        if self.state == "block":
            # La defensa reduce mucho el daño, pero consume stamina.
            blocked_damage = damage * 0.15
            stamina_damage = damage * 1.25

            self.health -= blocked_damage
            self.stamina = max(0, self.stamina - stamina_damage)

            # Guardia rota.
            if self.stamina <= 0:
                self.state = "stunned"
                self.stun_timer = 24

            return "blocked"

        self.health -= damage
        self.health = max(0, self.health)

        # Cross y hook tienen más posibilidad de aturdir.
        if attack_name in ("cross", "hook") and random.random() < 0.28:
            self.stun_timer = 10
            self.state = "stunned"

        if self.health <= 0:
            self.state = "ko"

        return "clean"

    # ---------- UPDATE ----------
    def update(self, opponent, game):
        if self.health <= 0:
            self.state = "ko"
            return

        if self.flash_timer > 0:
            self.flash_timer -= 1

        if self.stun_timer > 0:
            self.stun_timer -= 1
            self.state = "stunned"

            if self.stun_timer == 0:
                self.state = "idle"
            return

        # Regeneración.
        if self.state not in ("attack", "block"):
            self.stamina = min(self.max_stamina, self.stamina + 0.35)
        else:
            self.stamina = min(self.max_stamina, self.stamina + 0.08)

        if self.state == "block":
            # La guardia no dura eternamente si el jugador deja de mantenerla.
            if self.is_ai:
                self.ai_block_timer -= 1
                if self.ai_block_timer <= 0:
                    self.stop_block()
            return

        if self.state == "attack":
            self.attack_frame += 1

            data = self.attacks[self.attack]
            impact_frame = data["impact"]

            # IMPORTANTE:
            # El golpe se revisa UNA sola vez.
            if self.attack_frame == impact_frame and not self.has_hit:
                self.has_hit = True

                hitbox = self.attack_rect()
                if hitbox.colliderect(opponent.hurtbox()):
                    result = opponent.receive_hit(data["damage"], self.attack)
                    game.register_hit(self, opponent, self.attack, result)

            if self.attack_frame >= self.attack_duration:
                self.attack = None
                self.state = "idle"

        if self.is_ai:
            self.update_ai(opponent, game)

    # ---------- IA ----------
    def update_ai(self, player, game):
        if self.state in ("attack", "block", "stunned", "ko"):
            return

        self.ai_timer -= 1
        if self.ai_timer > 0:
            return

        self.ai_timer = random.randint(7, 15)

        distance = abs(self.x - player.x)

        # Si está bajo de stamina, se defiende o retrocede.
        if self.stamina < 20:
            if random.random() < 0.65:
                self.start_block()
                self.ai_block_timer = random.randint(15, 30)
            else:
                direction = 1 if self.x < player.x else -1
                self.move(direction * self.speed)
            return

        # Reacción a ataque del jugador.
        if player.state == "attack":
            if distance < 150 and random.random() < 0.45:
                self.start_block()
                self.ai_block_timer = random.randint(12, 24)
                return

        # Acercarse.
        if distance > 125:
            direction = -1 if self.x > player.x else 1
            self.move(direction * self.speed)
            return

        # Si está demasiado pegado, separarse un poco.
        if distance < 55:
            direction = 1 if self.x > player.x else -1
            self.move(direction * self.speed)
            return

        # Zona de ataque.
        choice = random.random()

        if choice < 0.42:
            self.start_attack("jab")
        elif choice < 0.70:
            self.start_attack("cross")
        elif choice < 0.86:
            self.start_attack("hook")
        elif choice < 0.95:
            self.start_block()
            self.ai_block_timer = random.randint(12, 25)
        else:
            # Pequeño movimiento defensivo.
            direction = 1 if random.random() < 0.5 else -1
            self.move(direction * self.speed)

    # ---------- DRAW ----------
    def draw(self, surface):
        # KO: cae de lado.
        if self.state == "ko":
            self.draw_ko(surface)
            return

        body = self.body_rect()

        # Parpadeo al recibir golpe.
        skin = WHITE if self.flash_timer > 0 else SKIN

        # Sombra.
        pygame.draw.ellipse(
            surface,
            (15, 15, 18),
            (body.x - 12, FLOOR_Y - 7, 74, 14)
        )

        # Piernas.
        pygame.draw.rect(surface, skin, (body.x + 7, body.y + 72, 13, 48))
        pygame.draw.rect(surface, skin, (body.x + 30, body.y + 72, 13, 48))

        # Zapatos.
        pygame.draw.rect(surface, BLACK, (body.x + 3, body.y + 108, 21, 9))
        pygame.draw.rect(surface, BLACK, (body.x + 27, body.y + 108, 21, 9))

        # Shorts.
        pygame.draw.rect(
            surface,
            self.body_color,
            (body.x, body.y + 55, 50, 34)
        )

        # Torso.
        pygame.draw.rect(
            surface,
            skin,
            (body.x + 5, body.y + 20, 40, 42)
        )

        # Cabeza.
        head = pygame.Rect(body.x + 10, body.y - 10, 30, 32)
        pygame.draw.ellipse(surface, skin, head)

        # Pelo.
        pygame.draw.arc(
            surface,
            BLACK,
            head,
            math.pi,
            math.pi * 2,
            7
        )

        # Brazos.
        direction = -1 if self.facing_left else 1

        # Guante trasero.
        back_x = body.centerx - direction * 18
        back_y = body.y + 39

        if self.state == "block":
            back_y -= 24

        pygame.draw.circle(
            surface,
            self.glove_color,
            (int(back_x), int(back_y)),
            11
        )

        # Guante delantero.
        if self.state == "attack":
            glove = self.attack_rect()
        else:
            front_x = body.centerx + direction * 18
            front_y = body.y + 42

            if self.state == "block":
                front_y -= 28
                front_x -= direction * 8

            glove = pygame.Rect(
                int(front_x - 11),
                int(front_y - 11),
                22,
                22
            )

        pygame.draw.circle(
            surface,
            self.glove_color,
            glove.center,
            11
        )

        # Nombre pequeño sobre el peleador.
        name_img = SMALL.render(self.name, True, WHITE)
        surface.blit(
            name_img,
            (body.centerx - name_img.get_width() // 2, body.y - 42)
        )

    def draw_ko(self, surface):
        rect = pygame.Rect(
            int(self.x - 65),
            int(FLOOR_Y - 35),
            130,
            28
        )

        pygame.draw.ellipse(surface, SKIN, rect)
        pygame.draw.rect(
            surface,
            self.body_color,
            (rect.x + 35, rect.y, 60, rect.h)
        )

        pygame.draw.circle(
            surface,
            self.glove_color,
            (rect.right - 10, rect.centery),
            12
        )


# ============================================================
# GAME
# ============================================================

class Game:
    def __init__(self):
        self.player = None
        self.enemy = None

        self.state = "menu"
        self.round_number = 1
        self.round_time = 90 * FPS

        self.hit_pause = 0
        self.shake = 0

        self.message = ""
        self.message_timer = 0

        self.reset_fight()

    def reset_fight(self):
        self.player = Fighter(
            300,
            "YOGUI",
            False,
            False,
            BLUE,
            RED
        )

        self.enemy = Fighter(
            700,
            "RIVAL",
            True,
            True,
            DARK_RED,
            BLUE
        )

        self.round_time = 90 * FPS
        self.hit_pause = 0
        self.shake = 0
        self.message = ""
        self.message_timer = 0

    # ---------- EVENTOS ----------
    def register_hit(self, attacker, victim, attack_name, result):
        if result == "blocked":
            self.message = "BLOCK!"
            self.message_timer = 20
            self.shake = 2
        else:
            attacker.score += 1

            if attack_name == "cross":
                self.hit_pause = 5
                self.shake = 9
                self.message = "CROSS!"
            elif attack_name == "hook":
                self.hit_pause = 5
                self.shake = 8
                self.message = "HOOK!"
            else:
                self.hit_pause = 2
                self.shake = 4
                self.message = "JAB!"

            self.message_timer = 20

    # ---------- INPUT ----------
    def handle_input(self):
        keys = pygame.key.get_pressed()

        if self.state == "menu":
            if keys[pygame.K_RETURN] or keys[pygame.K_SPACE]:
                self.state = "fight"
            return

        if self.state == "gameover":
            if keys[pygame.K_r]:
                self.round_number = 1
                self.reset_fight()
                self.state = "fight"
            elif keys[pygame.K_ESCAPE]:
                self.state = "menu"
            return

        if self.state != "fight":
            return

        if self.player.health <= 0:
            return

        # No controlar al jugador durante un ataque.
        if self.player.state == "attack":
            return

        if keys[pygame.K_a]:
            self.player.move(-self.player.speed)
        elif keys[pygame.K_d]:
            self.player.move(self.player.speed)
        else:
            if self.player.state == "move":
                self.player.state = "idle"

        # Defensa.
        if keys[pygame.K_l]:
            self.player.start_block()
            return
        elif self.player.state == "block":
            self.player.stop_block()

        # Golpes.
        if keys[pygame.K_j]:
            self.player.start_attack("jab")
        elif keys[pygame.K_k]:
            self.player.start_attack("cross")
        elif keys[pygame.K_i]:
            self.player.start_attack("hook")

    # ---------- UPDATE ----------
    def update(self):
        if self.state != "fight":
            return

        if self.hit_pause > 0:
            self.hit_pause -= 1
            return

        if self.shake > 0:
            self.shake -= 1

        if self.message_timer > 0:
            self.message_timer -= 1

        self.round_time -= 1

        self.handle_input()

        self.player.update(self.enemy, self)
        self.enemy.update(self.player, self)

        # Evitar que se atraviesen.
        distance = abs(self.player.x - self.enemy.x)

        if distance < 52:
            midpoint = (self.player.x + self.enemy.x) / 2

            if self.player.x < self.enemy.x:
                self.player.x = midpoint - 27
                self.enemy.x = midpoint + 27
            else:
                self.player.x = midpoint + 27
                self.enemy.x = midpoint - 27

        self.player.x = clamp(self.player.x, RING_LEFT + 25, RING_RIGHT - 25)
        self.enemy.x = clamp(self.enemy.x, RING_LEFT + 25, RING_RIGHT - 25)

        # KO.
        if self.enemy.health <= 0:
            self.finish("¡YOGUI GANA POR K.O.!")
            return

        if self.player.health <= 0:
            self.finish("¡RIVAL GANA POR K.O.!")
            return

        # Fin del round por tiempo.
        if self.round_time <= 0:
            if self.player.health > self.enemy.health:
                self.finish("¡YOGUI GANA POR DECISIÓN!")
            elif self.enemy.health > self.player.health:
                self.finish("¡RIVAL GANA POR DECISIÓN!")
            else:
                self.finish("¡EMPATE!")

    def finish(self, text):
        self.message = text
        self.state = "gameover"

    # ---------- DRAW ----------
    def draw_background(self, surface):
        surface.fill(DARK)

        # Luces del estadio.
        for x in range(50, WIDTH, 100):
            pygame.draw.circle(surface, (70, 70, 85), (x, 55), 3)

        # Público simplificado.
        for row in range(3):
            for x in range(25, WIDTH, 35):
                offset = 12 if row % 2 else 0
                pygame.draw.circle(
                    surface,
                    (55 + row * 10, 55 + row * 10, 65 + row * 8),
                    (x + offset, 105 + row * 27),
                    8
                )

        # Zona del ring.
        pygame.draw.rect(
            surface,
            (28, 28, 35),
            (0, 170, WIDTH, FLOOR_Y - 170)
        )

        # Ring floor.
        pygame.draw.rect(
            surface,
            MAT,
            (RING_LEFT, FLOOR_Y - 5, RING_RIGHT - RING_LEFT, 12)
        )

        # Cuerdas.
        rope_ys = [235, 290, 345, 400]
        for y in rope_ys:
            pygame.draw.line(
                surface,
                ROPE,
                (RING_LEFT, y),
                (RING_RIGHT, y),
                5
            )

        # Postes.
        for x in (RING_LEFT, RING_RIGHT):
            pygame.draw.rect(
                surface,
                GRAY,
                (x - 7, 205, 14, FLOOR_Y - 205)
            )

        # Suelo.
        pygame.draw.rect(
            surface,
            (18, 18, 23),
            (0, FLOOR_Y + 7, WIDTH, HEIGHT - FLOOR_Y)
        )

    def draw_bar(self, x, y, w, h, value, color, reverse=False):
        pygame.draw.rect(SCREEN, BLACK, (x - 3, y - 3, w + 6, h + 6))
        pygame.draw.rect(SCREEN, DARK_RED, (x, y, w, h))

        filled = int(w * clamp(value / 100, 0, 1))

        if reverse:
            pygame.draw.rect(
                SCREEN,
                color,
                (x + w - filled, y, filled, h)
            )
        else:
            pygame.draw.rect(
                SCREEN,
                color,
                (x, y, filled, h)
            )

    def draw_hud(self):
        # Nombres.
        left_name = FONT.render("YOGUI", True, WHITE)
        right_name = FONT.render("RIVAL", True, WHITE)

        SCREEN.blit(left_name, (30, 22))
        SCREEN.blit(
            right_name,
            (WIDTH - right_name.get_width() - 30, 22)
        )

        # Vida.
        self.draw_bar(
            30, 55, 360, 22,
            self.player.health,
            GREEN
        )

        self.draw_bar(
            WIDTH - 390, 55, 360, 22,
            self.enemy.health,
            GREEN,
            True
        )

        # Stamina.
        self.draw_bar(
            30, 88, 250, 10,
            self.player.stamina,
            YELLOW
        )

        self.draw_bar(
            WIDTH - 280, 88, 250, 10,
            self.enemy.stamina,
            YELLOW,
            True
        )

        # Round y tiempo.
        round_img = SMALL.render(
            f"ROUND {self.round_number}",
            True,
            WHITE
        )
        SCREEN.blit(
            round_img,
            (WIDTH // 2 - round_img.get_width() // 2, 20)
        )

        seconds = max(0, self.round_time // FPS)
        time_img = BIG.render(
            f"{seconds:02d}",
            True,
            YELLOW
        )
        SCREEN.blit(
            time_img,
            (WIDTH // 2 - time_img.get_width() // 2, 48)
        )

        # Indicador de golpe.
        if self.message_timer > 0:
            msg = BIG.render(self.message, True, YELLOW)
            SCREEN.blit(
                msg,
                (WIDTH // 2 - msg.get_width() // 2, 145)
            )

        # Controles.
        controls = SMALL.render(
            "A/D Mover   J Jab   K Cross   I Hook   L Guardia",
            True,
            LIGHT_GRAY
        )
        SCREEN.blit(
            controls,
            (WIDTH // 2 - controls.get_width() // 2, HEIGHT - 30)
        )

    def draw_menu(self):
        SCREEN.fill(BLACK)

        title = HUGE.render("RING WARS", True, RED)
        SCREEN.blit(
            title,
            (WIDTH // 2 - title.get_width() // 2, 120)
        )

        sub = BIG.render("2D BOXING", True, WHITE)
        SCREEN.blit(
            sub,
            (WIDTH // 2 - sub.get_width() // 2, 205)
        )

        start = FONT.render(
            "ENTER / ESPACIO  -  COMENZAR",
            True,
            YELLOW
        )
        SCREEN.blit(
            start,
            (WIDTH // 2 - start.get_width() // 2, 300)
        )

        info = SMALL.render(
            "Derrota al rival antes de que termine el round.",
            True,
            LIGHT_GRAY
        )
        SCREEN.blit(
            info,
            (WIDTH // 2 - info.get_width() // 2, 350)
        )

    def draw_gameover(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        SCREEN.blit(overlay, (0, 0))

        title = BIG.render(self.message, True, YELLOW)
        SCREEN.blit(
            title,
            (WIDTH // 2 - title.get_width() // 2, 220)
        )

        restart = FONT.render(
            "R - Revancha       ESC - Menú",
            True,
            WHITE
        )
        SCREEN.blit(
            restart,
            (WIDTH // 2 - restart.get_width() // 2, 285)
        )

    def draw(self):
        # Screen shake.
        world = pygame.Surface((WIDTH, HEIGHT))
        self.draw_background(world)

        self.player.draw(world)
        self.enemy.draw(world)

        SCREEN.fill(BLACK)

        if self.shake > 0:
            strength = 5
            offset = (
                random.randint(-strength, strength),
                random.randint(-strength, strength)
            )
        else:
            offset = (0, 0)

        SCREEN.blit(world, offset)

        if self.state != "menu":
            self.draw_hud()

        if self.state == "menu":
            self.draw_menu()
        elif self.state == "gameover":
            self.draw_gameover()

        pygame.display.flip()

    # ---------- LOOP ----------
    def run(self):
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            self.update()
            self.draw()

            CLOCK.tick(FPS)

        pygame.quit()
        sys.exit()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    game = Game()
    game.run()
