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
        # 1) 식물들의 나이 업데이트 및 시들기/소멸 처리 (매 프레임 진행)
        plants = self.world.get_entities_with(PositionComponent, FoodComponent, RenderComponent)
        decayed_plants = []
        for plant in plants:
            food = self.world.get_component(plant, FoodComponent)
            
            # 모든 식물(풀 및 해조류)의 나이 증가
            food.age += dt
            
            if not food.is_seaweed:
                # 육지 식물(풀)만 180초(3분) 경과 시 시들기
                if food.age >= 180.0 and not food.is_wilted:
                    food.is_wilted = True
                    food.energy_value = 40.0 * (2.0 / 3.0) # 포만감 2/3로 감소
                    # 비주얼 변경: 갈색빛이 감도는 누런 색상으로 변경
                    render = self.world.get_component(plant, RenderComponent)
                    render.color = (150, 120, 60)
                    
            # 모든 식물은 300초(5분) 경과 시 소멸 및 재배치
            if food.age >= 300.0:
                decayed_plants.append(plant)
                    
        # 소멸한 식물 월드에서 제거 (제거되면 다음 스폰 타이밍에 맵 다른 곳에 자동 분산 스폰)
        for plant in decayed_plants:
            self.world.entities.remove(plant)
            for comp_type in list(self.world.components.keys()):
                if plant in self.world.components[comp_type]:
                    del self.world.components[comp_type][plant]

        # 2) 식물 리스폰 및 스폰 로직 (0.1초마다 실행)
        self.spawn_timer += dt
        if self.spawn_timer >= 0.1: 
            self.spawn_timer = 0.0
            
            current_plants = self.world.get_entities_with(FoodComponent)
            if len(current_plants) < self.max_plants:
                for _ in range(3): 
                    x = random.uniform(0, self.width)
                    y = random.uniform(0, self.height)
                    
                    biome = self.world_map.get_biome_at(x, y)
                    is_seaweed = False
                    if biome in (2, 4): # WATER or DEEP_WATER
                        if random.random() > 0.5: # 50% 확률로 해조류 스폰
                            continue
                        is_seaweed = True
                    elif biome == 1 or biome == 3: # DESERT or SNOW
                        if random.random() > 0.15: # 사막과 설원에는 15% 확률로만 자라남 (매우 희귀)
                            continue
                            
                    entity = self.world.create_entity()
                    self.world.add_component(entity, PositionComponent(x, y))
                    if is_seaweed:
                        self.world.add_component(entity, RenderComponent((50, 160, 120), 5))
                    else:
                        self.world.add_component(entity, RenderComponent((40, 150, 60), 6))
                    self.world.add_component(entity, FoodComponent(energy_value=40.0, is_seaweed=is_seaweed))
