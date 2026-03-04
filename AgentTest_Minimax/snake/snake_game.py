import pygame
import random
import sys

# 初始化pygame
pygame.init()

# 颜色定义
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 200, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# 游戏窗口大小
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 400

# 蛇和食物的大小
BLOCK_SIZE = 20

# 设置窗口
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption('贪吃蛇游戏')

# 时钟控制
clock = pygame.time.Clock()

# 字体
font = pygame.font.SysFont('arial', 25)
score_font = pygame.font.SysFont('arial', 20)

def draw_snake(snake_list):
    """绘制蛇"""
    for i, segment in enumerate(snake_list):
        if i == 0:  # 蛇头
            pygame.draw.rect(screen, GREEN, [segment[0], segment[1], BLOCK_SIZE, BLOCK_SIZE])
        else:
            pygame.draw.rect(screen, DARK_GREEN, [segment[0], segment[1], BLOCK_SIZE, BLOCK_SIZE])
        # 添加边框使分段更明显
        pygame.draw.rect(screen, BLACK, [segment[0], segment[1], BLOCK_SIZE, BLOCK_SIZE], 1)

def draw_food(food_x, food_y):
    """绘制食物"""
    pygame.draw.rect(screen, RED, [food_x, food_y, BLOCK_SIZE, BLOCK_SIZE])
    pygame.draw.rect(screen, YELLOW, [food_x, food_y, BLOCK_SIZE, BLOCK_SIZE], 2)

def draw_score(score):
    """显示分数"""
    score_surface = score_font.render(f'Score: {score}', True, WHITE)
    screen.blit(score_surface, (10, 10))

def draw_message(message, color):
    """显示消息"""
    text_surface = font.render(message, True, color)
    text_rect = text_surface.get_rect()
    text_rect.center = (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
    screen.blit(text_surface, text_rect)

def generate_food():
    """生成随机食物位置"""
    food_x = random.randrange(0, WINDOW_WIDTH - BLOCK_SIZE, BLOCK_SIZE)
    food_y = random.randrange(0, WINDOW_HEIGHT - BLOCK_SIZE, BLOCK_SIZE)
    return food_x, food_y

def game_loop():
    """游戏主循环"""
    game_over = False
    game_close = False
    
    # 蛇的初始位置
    x1 = WINDOW_WIDTH // 2
    y1 = WINDOW_HEIGHT // 2
    
    # 蛇的移动变化
    x1_change = 0
    y1_change = 0
    
    # 蛇的身体
    snake_List = []
    Length_of_snake = 1
    
    # 生成第一个食物
    food_x, food_y = generate_food()
    
    # 速度
    speed = 10
    
    while not game_over:
        
        # 游戏暂停/结束时的等待界面
        while game_close:
            screen.fill(BLACK)
            draw_message('Game Over! Press Q-Quit or C-Play Again', RED)
            draw_score(Length_of_snake - 1)
            pygame.display.update()
            
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        game_over = True
                        game_close = False
                    if event.key == pygame.K_c:
                        game_loop()
        
        # 键盘事件处理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_over = True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT and x1_change != BLOCK_SIZE:
                    x1_change = -BLOCK_SIZE
                    y1_change = 0
                elif event.key == pygame.K_RIGHT and x1_change != -BLOCK_SIZE:
                    x1_change = BLOCK_SIZE
                    y1_change = 0
                elif event.key == pygame.K_UP and y1_change != BLOCK_SIZE:
                    y1_change = -BLOCK_SIZE
                    x1_change = 0
                elif event.key == pygame.K_DOWN and y1_change != -BLOCK_SIZE:
                    y1_change = BLOCK_SIZE
                    x1_change = 0
                # 速度控制
                elif event.key == pygame.K_w:  # 加速
                    speed = min(20, speed + 2)
                elif event.key == pygame.K_s:  # 减速
                    speed = max(5, speed - 2)
        
        # 检查是否撞墙
        if x1 >= WINDOW_WIDTH or x1 < 0 or y1 >= WINDOW_HEIGHT or y1 < 0:
            game_close = True
        
        x1 += x1_change
        y1 += y1_change
        
        screen.fill(BLACK)
        draw_food(food_x, food_y)
        
        # 更新蛇的身体
        snake_Head = []
        snake_Head.append(x1)
        snake_Head.append(y1)
        snake_List.append(snake_Head)
        
        if len(snake_List) > Length_of_snake:
            del snake_List[0]
        
        # 检查是否撞到自己
        for x in snake_List[:-1]:
            if x == snake_Head:
                game_close = True
        
        draw_snake(snake_List)
        draw_score(Length_of_snake - 1)
        
        # 显示速度提示
        speed_text = score_font.render(f'Speed: {speed}', True, WHITE)
        screen.blit(speed_text, (WINDOW_WIDTH - 100, 10))
        
        pygame.display.update()
        
        # 检查是否吃到食物
        if x1 == food_x and y1 == food_y:
            food_x, food_y = generate_food()
            # 确保食物不会生成在蛇身上
            while [food_x, food_y] in snake_List:
                food_x, food_y = generate_food()
            Length_of_snake += 1
            # 吃到食物可以稍微加速
            if Length_of_snake % 3 == 0 and speed < 15:
                speed += 1
        
        clock.tick(speed)
    
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    game_loop()
