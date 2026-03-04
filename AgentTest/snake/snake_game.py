import sys
from random import randrange

import pygame


# Colors
BLACK = (18, 18, 18)
WHITE = (240, 240, 240)
GREEN = (70, 220, 120)
RED = (230, 80, 80)
YELLOW = (250, 220, 120)

# Game config
WIDTH, HEIGHT = 640, 480
GRID_SIZE = 20
FPS = 10


def spawn_food(snake):
    """Spawn food on an empty grid cell."""
    while True:
        pos = [randrange(0, WIDTH, GRID_SIZE), randrange(0, HEIGHT, GRID_SIZE)]
        if pos not in snake:
            return pos


def draw_text(surface, text, size, color, x, y):
    font = pygame.font.SysFont("consolas", size)
    surface.blit(font.render(text, True, color), (x, y))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake Game")
    clock = pygame.time.Clock()

    # Snake starts with 3 blocks moving right.
    snake = [[100, 100], [80, 100], [60, 100]]
    direction = [GRID_SIZE, 0]
    food = spawn_food(snake)
    score = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP and direction != [0, GRID_SIZE]:
                    direction = [0, -GRID_SIZE]
                elif event.key == pygame.K_DOWN and direction != [0, -GRID_SIZE]:
                    direction = [0, GRID_SIZE]
                elif event.key == pygame.K_LEFT and direction != [GRID_SIZE, 0]:
                    direction = [-GRID_SIZE, 0]
                elif event.key == pygame.K_RIGHT and direction != [-GRID_SIZE, 0]:
                    direction = [GRID_SIZE, 0]
                elif event.key == pygame.K_ESCAPE:
                    running = False

        # Move snake by inserting new head.
        new_head = [snake[0][0] + direction[0], snake[0][1] + direction[1]]

        # Check wall collision.
        if new_head[0] < 0 or new_head[0] >= WIDTH or new_head[1] < 0 or new_head[1] >= HEIGHT:
            break

        # Check self collision.
        if new_head in snake:
            break

        snake.insert(0, new_head)

        # Eat food or move tail.
        if new_head == food:
            score += 1
            food = spawn_food(snake)
        else:
            snake.pop()

        # Draw
        screen.fill(BLACK)
        pygame.draw.rect(screen, GREEN, pygame.Rect(food[0], food[1], GRID_SIZE, GRID_SIZE))
        for part in snake:
            pygame.draw.rect(screen, WHITE, pygame.Rect(part[0], part[1], GRID_SIZE, GRID_SIZE))
        draw_text(screen, f"Score: {score}", 24, YELLOW, 8, 8)
        pygame.display.flip()
        clock.tick(FPS)

    # Game over screen for a brief moment.
    screen.fill(BLACK)
    draw_text(screen, "Game Over", 42, RED, WIDTH // 2 - 110, HEIGHT // 2 - 35)
    draw_text(screen, f"Final Score: {score}", 24, WHITE, WIDTH // 2 - 85, HEIGHT // 2 + 15)
    pygame.display.flip()
    pygame.time.delay(1200)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
