import math
import random
import pygame
from ecs.components import PositionComponent, RenderComponent, DNAComponent, HealthComponent, FoodComponent

class SurvivalSystem:
    def __init__(self, world, world_map, world_width, world_height, max_population=500, logger=None):
        self.world = world
        self.world_map = world_map
        self.width = world_width
        self.height = world_height
        self.max_population = max_population
        self.logger = logger

    def update(self, dt):
        animals = self.world.get_entities_with(PositionComponent, DNAComponent, HealthComponent)
        foods = self.world.get_entities_with(PositionComponent, FoodComponent)
        
        dead_foods = set()
        mated_pairs = set() 
        new_borns = []
        
        for animal in animals:
            if animal in mated_pairs:
                continue
                
            pos = self.world.get_component(animal, PositionComponent)
            dna = self.world.get_component(animal, DNAComponent)
            health = self.world.get_component(animal, HealthComponent)
            
            if health.mating_cooldown > 0:
                health.mating_cooldown -= dt
                
            sensor_radius = 200.0
            speed = 50 * dna.speed_gene
            
            # 지형 속도 패널티 적용
            current_biome = self.world_map.get_biome_at(pos.x, pos.y)
            if current_biome == 3: # SNOW
                # 털이 두꺼울수록(1.0) 정상 속도(1.0), 얇을수록(0.0) 50% 속도
                speed *= (0.5 + 0.5 * getattr(dna, 'fur_gene', 0.5))
                
            wants_to_mate = (health.energy >= health.max_energy * 1.0 and health.age > 20.0 and health.mating_cooldown <= 0)
            
            prev_x, prev_y = pos.x, pos.y
            
            if pos.blocked_timer > 0:
                pos.blocked_timer -= dt
                wants_to_mate = False # 우회 중에는 짝짓기 무시
            
            if wants_to_mate and len(animals) + len(new_borns) < self.max_population:
                nearest_mate = None
                min_dist = float('inf')
                
                for other in animals:
                    if other == animal or other in mated_pairs: continue
                    other_health = self.world.get_component(other, HealthComponent)
                    other_wants_to_mate = (other_health.energy >= other_health.max_energy * 1.0 and other_health.age > 20.0 and other_health.mating_cooldown <= 0)
                    
                    if other_wants_to_mate:
                        o_pos = self.world.get_component(other, PositionComponent)
                        dist = math.hypot(pos.x - o_pos.x, pos.y - o_pos.y)
                        if dist < min_dist and dist < sensor_radius:
                            min_dist = dist
                            nearest_mate = other
                            
                if nearest_mate is not None:
                    m_pos = self.world.get_component(nearest_mate, PositionComponent)
                    dx = m_pos.x - pos.x
                    dy = m_pos.y - pos.y
                    length = math.hypot(dx, dy)
                    
                    if length < 15.0: 
                        mated_pairs.add(animal)
                        mated_pairs.add(nearest_mate)
                        m_health = self.world.get_component(nearest_mate, HealthComponent)
                        m_dna = self.world.get_component(nearest_mate, DNAComponent)
                        
                        health.energy -= health.max_energy * 0.5
                        m_health.energy -= m_health.max_energy * 0.5
                        health.mating_cooldown = 15.0
                        m_health.mating_cooldown = 15.0
                        
                        new_borns.append((pos, dna, m_dna, animal, nearest_mate))
                    else: 
                        pos.x += (dx / length) * speed * dt
                        pos.y += (dy / length) * speed * dt
                        
                    if self.world_map.get_biome_at(pos.x, pos.y) in (2, 4): 
                        pos.x, pos.y = prev_x, prev_y
                        
                        best_angle = pos.wander_angle + math.pi
                        for angle in [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]:
                            tx = pos.x + math.cos(angle) * 30
                            ty = pos.y + math.sin(angle) * 30
                            if self.world_map.get_biome_at(tx, ty) not in (2, 4):
                                best_angle = angle
                                break
                                
                        pos.wander_angle = best_angle
                        pos.blocked_timer = 1.0 + (getattr(dna, 'size_gene', 0.5) * 2.0)
                    continue 
                    
            nearest_food = None
            min_dist = float('inf')
            
            if health.energy < health.max_energy * 1.2 and pos.blocked_timer <= 0:
                for food in foods:
                    if food in dead_foods: continue
                    f_pos = self.world.get_component(food, PositionComponent)
                    dist = math.hypot(pos.x - f_pos.x, pos.y - f_pos.y)
                    
                    if dist < min_dist and dist < sensor_radius:
                        min_dist = dist
                        nearest_food = food
            
            if nearest_food is not None:
                f_pos = self.world.get_component(nearest_food, PositionComponent)
                dx = f_pos.x - pos.x
                dy = f_pos.y - pos.y
                length = math.hypot(dx, dy)
                
                if length < 10.0:
                    food_comp = self.world.get_component(nearest_food, FoodComponent)
                    health.energy += food_comp.energy_value
                    if health.energy > health.max_energy * 2: 
                        health.energy = health.max_energy * 2
                    dead_foods.add(nearest_food)
                else:
                    pos.x += (dx / length) * speed * dt
                    pos.y += (dy / length) * speed * dt
            else:
                pos.wander_timer -= dt
                if pos.wander_timer <= 0:
                    pos.wander_angle = random.uniform(0, math.pi * 2)
                    pos.wander_timer = random.uniform(2.0, 5.0) 
                
                pos.x += math.cos(pos.wander_angle) * speed * dt
                pos.y += math.sin(pos.wander_angle) * speed * dt
                
            if self.world_map.get_biome_at(pos.x, pos.y) in (2, 4):
                pos.x, pos.y = prev_x, prev_y
                
                best_angle = pos.wander_angle + math.pi
                for angle in [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]:
                    tx = pos.x + math.cos(angle) * 30
                    ty = pos.y + math.sin(angle) * 30
                    if self.world_map.get_biome_at(tx, ty) not in (2, 4):
                        best_angle = angle
                        break
                        
                pos.wander_angle = best_angle
                pos.blocked_timer = 1.0 + (getattr(dna, 'size_gene', 0.5) * 2.0)
                
            if pos.x < 0: pos.x = 0
            if pos.x > self.width: pos.x = self.width
            if pos.y < 0: pos.y = 0
            if pos.y > self.height: pos.y = self.height
            
        for f in dead_foods:
            if f in self.world.entities:
                self.world.entities.remove(f)
                for comp_type in list(self.world.components.keys()):
                    if f in self.world.components[comp_type]:
                        del self.world.components[comp_type][f]
                        
        for p_pos, dna1, dna2, p1_id, p2_id in new_borns:
            entity = self.world.create_entity()
            new_x = p_pos.x + random.uniform(-20, 20)
            new_y = p_pos.y + random.uniform(-20, 20)
            
            if self.world_map.get_biome_at(new_x, new_y) in (2, 4):
                new_x, new_y = p_pos.x, p_pos.y
                
            if self.logger:
                 biome_val = self.world_map.get_biome_at(new_x, new_y)
                 biome_name = {0: "초원", 1: "사막", 2: "바다", 3: "설원", 4: "깊은 물"}.get(biome_val, "미지")
                 self.logger.add_log(f"[출산] ID:{p1_id} & {p2_id}의 자손 ({biome_name})", entity_id=entity)
                
            self.world.add_component(entity, PositionComponent(new_x, new_y))
            
            def mutate(val):
                # 10% 확률로 큰 돌연변이, 나머지는 ±15% 일반 돌연변이
                if random.random() < 0.1:
                    return val * random.uniform(0.5, 1.5)
                return val * random.uniform(0.85, 1.15)
                
            base_size = random.choice([dna1.size_gene, dna2.size_gene])
            base_speed = random.choice([dna1.speed_gene, dna2.speed_gene])
            base_meta = random.choice([dna1.metabolism_gene, dna2.metabolism_gene])
            base_color = random.choice([dna1.color_gene, dna2.color_gene])
            base_fur = random.choice([getattr(dna1, 'fur_gene', 0.5), getattr(dna2, 'fur_gene', 0.5)])
            
            new_size = mutate(base_size)
            new_speed = mutate(base_speed)
            new_meta = mutate(base_meta)
            
            # 털 밀도는 0.0 ~ 1.0 사이이므로 덧셈/뺄셈 방식의 돌연변이 적용 (최대 ±0.25)
            fur_mutation = random.uniform(-0.25, 0.25)
            new_fur = max(0.0, min(1.0, base_fur + fur_mutation))
            
            r, g, b = base_color
            new_r = max(0, min(255, r + random.randint(-15, 15)))
            new_g = max(0, min(255, g + random.randint(-15, 15)))
            new_b = max(0, min(255, b + random.randint(-15, 15)))
            new_color = (new_r, new_g, new_b)
            
            self.world.add_component(entity, DNAComponent(new_size, new_speed, new_color, new_meta, new_fur))
            self.world.add_component(entity, RenderComponent(new_color, int(16 * new_size)))
            
            self.world.add_component(entity, HealthComponent(
                current_health=30.0, max_health=100.0,
                age=0.0, lifespan=random.uniform(150, 300),
                energy=50.0, max_energy=100.0,
                mating_cooldown=10.0 
            ))


class MetabolismSystem:
    def __init__(self, world, world_map, logger=None):
        self.world = world
        self.world_map = world_map
        self.logger = logger

    def update(self, dt):
        entities = self.world.get_entities_with(HealthComponent, DNAComponent, PositionComponent)
        dead_entities = []
        for entity in entities:
            health = self.world.get_component(entity, HealthComponent)
            dna = self.world.get_component(entity, DNAComponent)
            pos = self.world.get_component(entity, PositionComponent)
            
            health.age += dt
            
            drain_mult = 4.0
            biome = self.world_map.get_biome_at(pos.x, pos.y)
            fur_gene = getattr(dna, 'fur_gene', 0.5)
            
            if biome == 1: # DESERT
                # 털이 두꺼울수록 열사병 (최대 20배)
                drain_mult = 4.0 + (fur_gene * 16.0)
            elif biome == 3: # SNOW
                # 털이 얇을수록 동사 (최대 20배)
                drain_mult = 4.0 + ((1.0 - fur_gene) * 16.0)
            
            energy_drain = (dna.size_gene * 0.5 + dna.speed_gene * 1.5) * dna.metabolism_gene * drain_mult * dt
            health.energy -= energy_drain
            
            if health.energy <= 0:
                health.energy = 0
                health.current_health -= 5 * dt
            else:
                health.current_health += 2 * dt
                if health.current_health > health.max_health:
                    health.current_health = health.max_health
                
            if health.age > health.lifespan:
                health.current_health -= 20 * dt
                
            if health.current_health <= 0:
                dead_entities.append(entity)
                if self.logger:
                    biome_val = self.world_map.get_biome_at(pos.x, pos.y)
                    biome_name = {0: "초원", 1: "사막", 2: "바다", 3: "설원", 4: "깊은 물"}.get(biome_val, "미지")
                    if health.age > health.lifespan:
                        self.logger.add_log(f"[자연사] ID:{entity} ({biome_name}에서 수명을 다함)")
                    else:
                        self.logger.add_log(f"[아사] ID:{entity} ({biome_name}에서 굶어 죽음)")
                
        for entity in dead_entities:
            self.world.entities.remove(entity)
            for comp_type in list(self.world.components.keys()):
                if entity in self.world.components[comp_type]:
                    del self.world.components[comp_type][entity]

class RenderSystem:
    def __init__(self, world, screen, camera, world_width, world_height):
        self.world = world
        self.screen = screen
        self.camera = camera
        self.world_width = world_width
        self.world_height = world_height

    def update(self):
        # 월드 보더 렌더링 (타일 렌더링 위에 겹치도록)
        bx, by = self.camera.apply(0, 0)
        bw = self.camera.apply_size(self.world_width)
        bh = self.camera.apply_size(self.world_height)
        border_thickness = max(2, self.camera.apply_size(10))
        pygame.draw.rect(self.screen, (200, 70, 70), pygame.Rect(bx, by, bw, bh), border_thickness)
        
        entities = self.world.get_entities_with(PositionComponent, RenderComponent)
        for entity in entities:
            pos = self.world.get_component(entity, PositionComponent)
            render = self.world.get_component(entity, RenderComponent)
            
            screen_x, screen_y = self.camera.apply(pos.x, pos.y)
            screen_size = self.camera.apply_size(render.size)
            
            if -screen_size <= screen_x <= self.screen.get_width() + screen_size and -screen_size <= screen_y <= self.screen.get_height() + screen_size:
                rect = pygame.Rect(int(screen_x - screen_size/2), int(screen_y - screen_size/2), screen_size, screen_size)
                
                if self.world.get_component(entity, FoodComponent):
                    # 식량은 테두리가 있는 원으로 그림 (가시성 증가)
                    pygame.draw.circle(self.screen, render.color, (int(screen_x), int(screen_y)), max(2, screen_size // 2))
                    pygame.draw.circle(self.screen, (20, 80, 20), (int(screen_x), int(screen_y)), max(2, screen_size // 2), 1)
                else:
                    pygame.draw.rect(self.screen, render.color, rect)
                    
                    dna = self.world.get_component(entity, DNAComponent)
                    if dna and hasattr(dna, 'fur_gene'):
                        fur_thickness = max(1, int((screen_size / 3) * dna.fur_gene))
                        if fur_thickness > 0 and dna.fur_gene > 0.1:
                            fur_color = (180, 180, 180)
                            pygame.draw.rect(self.screen, fur_color, rect, fur_thickness)
                    
                    if self.camera.target_entity == entity:
                        pygame.draw.circle(self.screen, (255, 255, 0), (int(screen_x), int(screen_y)), max(3, screen_size//3))
