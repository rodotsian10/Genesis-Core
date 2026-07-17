import pygame
import sys
import random
from ecs.core import World
from ecs.components import PositionComponent, RenderComponent, HealthComponent, DNAComponent, FoodComponent
from ecs.systems import MetabolismSystem, RenderSystem, SurvivalSystem
from ecs.systems_environment import PlantSpawnSystem
from ui.inspector import InspectorUI
from camera import Camera
from logger import EventLogger
from world_map import WorldMap

def main():
    pygame.init()
    width, height = 1200, 720
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Genesis Core - Phase 4 (Biomes Update)")
    clock = pygame.time.Clock()
    
    world_width, world_height = 4000, 4000
    camera = Camera(width, height, world_width, world_height)
    
    world = World()
    world_map = WorldMap(world_width, world_height)
    ui_panel_width = 300
    
    logger = EventLogger(max_logs=100)
    
    survival_system = SurvivalSystem(world, world_map, world_width, world_height, max_population=500, logger=logger)
    metabolism_system = MetabolismSystem(world, world_map, logger=logger)
    plant_system = PlantSpawnSystem(world, world_map, world_width, world_height, max_plants=600)
    render_system = RenderSystem(world, screen, camera, world_width, world_height)
    
    ui = InspectorUI(world, width, height, ui_panel_width)
    ui.logger = logger
    
    # 초기 스폰은 풀밭(GRASS)에만 안전하게 스폰
    spawn_count = 0
    while spawn_count < 100:
        rx, ry = random.uniform(0, world_width), random.uniform(0, world_height)
        if world_map.get_biome_at(rx, ry) == 0: # GRASS
            entity = world.create_entity()
            world.add_component(entity, PositionComponent(rx, ry))
            
            size_gene = random.uniform(0.5, 2.0)
            speed_gene = random.uniform(0.5, 2.0)
            metabolism_gene = random.uniform(0.8, 1.2)
            
            colors = [(138, 182, 102), (217, 160, 102), (200, 100, 100), (100, 150, 200), (220, 200, 100)]
            color_gene = random.choice(colors)
            fur_gene = 0.5
            
            world.add_component(entity, DNAComponent(size_gene, speed_gene, color_gene, metabolism_gene, fur_gene))
            actual_size = int(16 * size_gene)
            world.add_component(entity, RenderComponent(color_gene, actual_size))
            
            world.add_component(entity, HealthComponent(
                current_health=100.0, max_health=100.0, 
                age=random.uniform(0, 50), lifespan=random.uniform(100, 250),
                energy=100.0, max_energy=100.0
            ))
            spawn_count += 1
        
    running = True
    is_panning = False
    
    while running:
        dt = clock.tick(60) / 1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: 
                    ui.handle_click(event.pos[0], event.pos[1], camera)
                elif event.button == 3: 
                    if event.pos[0] < width - ui_panel_width:
                        is_panning = True
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    is_panning = False
            elif event.type == pygame.MOUSEMOTION:
                if is_panning:
                    camera.handle_input(event.rel[0], event.rel[1])
            elif event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                if mouse_x < width - ui_panel_width:
                    camera.handle_zoom(event.y * 0.1, mouse_x, mouse_y)
                else:
                    if hasattr(ui, 'handle_scroll'):
                        ui.handle_scroll(event.y)
                    
        camera.update()
        plant_system.update(dt)
        survival_system.update(dt)
        metabolism_system.update(dt)
        
        # 렌더링 파이프라인
        screen.fill((0, 0, 0)) # 배경 초기화
        world_map.render(screen, camera) # 타일맵(지형) 먼저 렌더링
        render_system.update() # 그 위에 생명체와 식량 렌더링
        ui.render(screen) # 가장 위에 UI 렌더링
        
        font = pygame.font.SysFont('malgungothic', 16)
        pop_count = len(world.get_entities_with(DNAComponent))
        food_count = len(world.get_entities_with(FoodComponent))
        info_text = font.render(f"인구: {pop_count}/500 | 식량: {food_count}/600", True, (255, 255, 255))
        screen.blit(info_text, (10, 10))
        
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
