import random
from ecs.components import PositionComponent, RenderComponent, FoodComponent

class PlantSpawnSystem:
    def __init__(self, world, world_map, world_width, world_height, max_plants=800):
        self.world = world
        self.world_map = world_map
        self.width = world_width
        self.height = world_height
        self.max_plants = max_plants
        self.spawn_timer = 0.0

    def update(self, dt):
        self.spawn_timer += dt
        if self.spawn_timer >= 0.1: 
            self.spawn_timer = 0.0
            
            plants = self.world.get_entities_with(FoodComponent)
            if len(plants) < self.max_plants:
                for _ in range(3): 
                    x = random.uniform(0, self.width)
                    y = random.uniform(0, self.height)
                    
                    biome = self.world_map.get_biome_at(x, y)
                    if biome in (2, 4): # WATER or DEEP_WATER
                        continue # 물 위에는 자라지 않음
                    elif biome == 1 or biome == 3: # DESERT or SNOW
                        if random.random() > 0.15: # 사막과 설원에는 15% 확률로만 자라남 (매우 희귀)
                            continue
                            
                    entity = self.world.create_entity()
                    self.world.add_component(entity, PositionComponent(x, y))
                    self.world.add_component(entity, RenderComponent((40, 150, 60), 6))
                    self.world.add_component(entity, FoodComponent(energy_value=40.0))
