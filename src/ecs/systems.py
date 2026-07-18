import math
import random
import pygame
try:
    import genesis_core
    _RUST_OK = True
except ImportError:
    _RUST_OK = False
from ecs.components import PositionComponent, RenderComponent, DNAComponent, HealthComponent, FoodComponent

class SurvivalSystem:
    def __init__(self, world, world_map, world_width, world_height, max_population=500, logger=None, enable_amphibians=True):
        self.world = world
        self.world_map = world_map
        self.width = world_width
        self.height = world_height
        self.max_population = max_population
        self.logger = logger
        self.enable_amphibians = enable_amphibians

    def update(self, dt):
        animals = self.world.get_entities_with(PositionComponent, DNAComponent, HealthComponent)
        foods = self.world.get_entities_with(PositionComponent, FoodComponent)
        
        dead_foods = set()
        mated_pairs = set() 
        new_borns = []
        
        foods_data = []
        for food in foods:
            f_pos = self.world.get_component(food, PositionComponent)
            f_biome = self.world_map.get_biome_at(f_pos.x, f_pos.y)
            foods_data.append((food, f_pos.x, f_pos.y, f_biome))
        
        for animal in animals:
            if animal in mated_pairs:
                continue
                
            # 조류 및 알은 BirdSystem이 독자적으로 처리하므로 일반 루프에서 제외
            _dna = self.world.get_component(animal, DNAComponent)
            if _dna is not None and (getattr(_dna, 'is_bird', False) or getattr(_dna, 'is_egg', False)):
                continue

            pos = self.world.get_component(animal, PositionComponent)
            dna = self.world.get_component(animal, DNAComponent)
            health = self.world.get_component(animal, HealthComponent)
            
            if health.mating_cooldown > 0:
                health.mating_cooldown -= dt
                
            sensor_radius = 300.0
            if health.energy < health.max_energy * 0.5:
                sensor_radius = 600.0
            speed = 50 * dna.speed_gene
            aquatic_gene = getattr(dna, 'aquatic_gene', 0.0)
            curiosity = getattr(dna, 'curiosity_gene', 0.5)
            is_aquatic = aquatic_gene >= 0.5
            fur_gene = getattr(dna, 'fur_gene', 0.5)
            
            def is_safe_biome(b_val):
                if is_aquatic:
                    if b_val not in (2, 4): return False
                else:
                    if b_val in (2, 4): return False
                if b_val == 1 and fur_gene > 0.2:
                    return False
                if b_val == 3 and fur_gene < 0.8:
                    return False
                return True
            
            current_biome = self.world_map.get_biome_at(pos.x, pos.y)
            if current_biome == 1:
                fur_gene = getattr(dna, 'fur_gene', 0.5)
                if fur_gene > 0.2:
                    speed *= (0.5 + 0.5 * (1.0 - fur_gene))
            elif current_biome == 3:
                fur_gene = getattr(dna, 'fur_gene', 0.5)
                if fur_gene < 0.8:
                    speed *= (0.5 + 0.5 * fur_gene)

            is_escaping_breath = getattr(health, 'is_escaping_breath', False)
            if health.breath <= health.max_breath * 0.4:
                health.is_escaping_breath = True
                is_escaping_breath = True
            elif is_escaping_breath and health.breath >= health.max_breath:
                health.is_escaping_breath = False
                is_escaping_breath = False
            
            survival_escape = is_escaping_breath
            prev_x, prev_y = pos.x, pos.y
            
            if pos.blocked_timer > 0:
                pos.blocked_timer -= dt

            life_pct = health.age / max(health.lifespan, 1.0)
            
            if life_pct < 0.6:
                effective_curiosity = curiosity
            elif life_pct < 0.8:
                effective_curiosity = curiosity * (1.0 - (life_pct - 0.6) / 0.2)
            else:
                effective_curiosity = 0.0
            
            effective_curiosity = max(0.05, effective_curiosity)
            desperate_mating_mode = (life_pct >= 0.9 and getattr(health, 'mated_count', 0) == 0)
            wants_to_mate = (life_pct >= 0.6 and health.energy >= health.max_energy * 0.7 and health.mating_cooldown <= 0)

            if survival_escape and not desperate_mating_mode:
                current_biome = self.world_map.get_biome_at(pos.x, pos.y)
                if is_safe_biome(current_biome):
                    continue
                
                speed *= 1.2
                best_angle = None
                for check_dist in [40.0, 120.0, 250.0, 450.0]:
                    for angle in [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]:
                        tx = pos.x + math.cos(angle) * check_dist
                        ty = pos.y + math.sin(angle) * check_dist
                        biome_t = self.world_map.get_biome_at(tx, ty)
                        if is_safe_biome(biome_t):
                            best_angle = angle
                            break
                    if best_angle is not None:
                        break
                if best_angle is None:
                    best_angle = random.uniform(0, math.pi * 2)
                target_angle = best_angle
                angle_diff = (target_angle - pos.wander_angle + math.pi) % (2 * math.pi) - math.pi
                pos.wander_angle += angle_diff * 8.0 * dt
                pos.x += math.cos(pos.wander_angle) * speed * dt
                pos.y += math.sin(pos.wander_angle) * speed * dt
                continue
            
            is_hungry = (health.energy < health.max_energy * 0.8)
            
            nearest_food = None
            if health.energy < health.max_energy * 1.2:
                if _RUST_OK:
                    active_foods = [fd for fd in foods_data if fd[0] not in dead_foods]
                    nearest_food = genesis_core.find_nearest_food(
                        pos.x, pos.y,
                        is_aquatic, fur_gene, effective_curiosity,
                        active_foods
                    )
                else:
                    min_food_dist_sq = float('inf')
                    for food in foods:
                        if food in dead_foods: continue
                        f_pos = self.world.get_component(food, PositionComponent)
                        dx = pos.x - f_pos.x; dy = pos.y - f_pos.y
                        dist_sq = dx*dx + dy*dy
                        if dist_sq < min_food_dist_sq:
                            min_food_dist_sq = dist_sq
                            nearest_food = food

            action_taken = False

            if is_hungry and nearest_food is not None and not desperate_mating_mode:
                f_pos = self.world.get_component(nearest_food, PositionComponent)
                dx = f_pos.x - pos.x
                dy = f_pos.y - pos.y
                length = math.hypot(dx, dy)
                render_comp = self.world.get_component(animal, RenderComponent)
                eat_dist = max(20.0, render_comp.size * 1.2)
                
                if length < eat_dist:
                    food_comp = self.world.get_component(nearest_food, FoodComponent)
                    health.energy += food_comp.energy_value
                    if health.energy > health.max_energy * 2: 
                        health.energy = health.max_energy * 2
                    dead_foods.add(nearest_food)
                else:
                    move_dist = speed * dt
                    if move_dist >= length:
                        health.energy += self.world.get_component(nearest_food, FoodComponent).energy_value
                        if health.energy > health.max_energy * 2:
                            health.energy = health.max_energy * 2
                        dead_foods.add(nearest_food)
                        pos.x, pos.y = f_pos.x, f_pos.y
                    else:
                        target_dx = dx / length
                        target_dy = dy / length
                        check_x = pos.x + target_dx * 60.0
                        check_y = pos.y + target_dy * 60.0
                        future_biome = self.world_map.get_biome_at(check_x, check_y)
                        
                        if not is_safe_biome(future_biome):
                            best_steer_x, best_steer_y = target_dx, target_dy
                            best_score = -9999.0
                            for i in range(16):
                                angle = math.atan2(dy, dx) + (i - 8) * (math.pi / 8.0)
                                sx = math.cos(angle)
                                sy = math.sin(angle)
                                tx = pos.x + sx * 50.0
                                ty = pos.y + sy * 50.0
                                tb = self.world_map.get_biome_at(tx, ty)
                                if is_safe_biome(tb):
                                    dot_product = sx * target_dx + sy * target_dy
                                    if dot_product > best_score:
                                        best_score = dot_product
                                        best_steer_x, best_steer_y = sx, sy
                            target_dx, target_dy = best_steer_x, best_steer_y
                        
                        pos.x += target_dx * move_dist
                        pos.y += target_dy * move_dist
                action_taken = True

            if not action_taken and len(animals) + len(new_borns) < self.max_population:
                scan_radius = self.width * 2 if desperate_mating_mode else (sensor_radius if wants_to_mate else 15.0)
                nearest_mate = None
                
                if _RUST_OK:
                    candidates = []
                    for other in animals:
                        if other == animal or other in mated_pairs:
                            continue
                        o_pos = self.world.get_component(other, PositionComponent)
                        o_h = self.world.get_component(other, HealthComponent)
                        o_biome = self.world_map.get_biome_at(o_pos.x, o_pos.y)
                        candidates.append((other, o_pos.x, o_pos.y, o_biome,
                                           o_h.mating_cooldown, o_h.energy, o_h.max_energy))
                    res = genesis_core.find_nearest_mate(
                        animal, pos.x, pos.y,
                        is_aquatic, fur_gene, scan_radius, desperate_mating_mode,
                        candidates, list(mated_pairs)
                    )
                    if res is not None:
                        nearest_mate = res[0]
                else:
                    min_mate_dist = float('inf')
                    for other in animals:
                        if other == animal or other in mated_pairs: continue
                        o_pos = self.world.get_component(other, PositionComponent)
                        if not desperate_mating_mode:
                            if abs(pos.x - o_pos.x) > scan_radius or abs(pos.y - o_pos.y) > scan_radius:
                                continue
                        o_health = self.world.get_component(other, HealthComponent)
                        req = o_health.max_energy * 0.3 if desperate_mating_mode else o_health.max_energy * 0.5
                        if o_health.mating_cooldown <= 0 and o_health.energy >= req:
                            dist = math.hypot(pos.x - o_pos.x, pos.y - o_pos.y)
                            if dist < min_mate_dist and dist < scan_radius:
                                min_mate_dist = dist
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
                        
                        health.mated_count = getattr(health, 'mated_count', 0) + 1
                        m_health.mated_count = getattr(m_health, 'mated_count', 0) + 1
                        
                        new_borns.append((pos, dna, m_dna, animal, nearest_mate))
                        
                        if health.energy <= 0:
                            health.current_health = 0.0
                            if self.logger:
                                self.logger.add_log(f"[단회번식] ID:{animal} 최후의 번식 후 탈진 사망", entity_id=animal, color=(255, 105, 180), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                                self.logger.logs[-1]["dead_stat"] = {
                                    "id": animal, "age": health.age, "lifespan": health.lifespan,
                                    "max_health": health.max_health, "max_energy": health.max_energy,
                                    "size": dna.size_gene, "speed": dna.speed_gene, "meta": dna.metabolism_gene,
                                    "fur": getattr(dna, 'fur_gene', 0.5), "aquatic": getattr(dna, 'aquatic_gene', 0.0),
                                    "curiosity": getattr(dna, 'curiosity_gene', 0.5), "generation": getattr(dna, 'generation', 1),
                                    "is_mutated": getattr(dna, 'is_mutated', False), "death_cause": "단회번식 탈진사"
                                }
                        if m_health.energy <= 0:
                            m_health.current_health = 0.0
                            if self.logger:
                                m_dna = self.world.get_component(nearest_mate, DNAComponent)
                                m_aquatic = getattr(m_dna, 'aquatic_gene', 0.0) >= 0.5
                                self.logger.add_log(f"[단회번식] ID:{nearest_mate} 최후의 번식 후 탈진 사망", entity_id=nearest_mate, color=(255, 105, 180), x=m_pos.x, y=m_pos.y, is_aquatic=m_aquatic)
                                self.logger.logs[-1]["dead_stat"] = {
                                    "id": nearest_mate, "age": m_health.age, "lifespan": m_health.lifespan,
                                    "max_health": m_health.max_health, "max_energy": m_health.max_energy,
                                    "size": m_dna.size_gene, "speed": m_dna.speed_gene, "meta": m_dna.metabolism_gene,
                                    "fur": getattr(m_dna, 'fur_gene', 0.5), "aquatic": getattr(m_dna, 'aquatic_gene', 0.0),
                                    "curiosity": getattr(m_dna, 'curiosity_gene', 0.5), "generation": getattr(m_dna, 'generation', 1),
                                    "is_mutated": getattr(m_dna, 'is_mutated', False), "death_cause": "단회번식 탈진사"
                                }
                        action_taken = True
                    elif wants_to_mate or desperate_mating_mode:
                        target_dx = dx / length
                        target_dy = dy / length
                        if not desperate_mating_mode:
                            check_x = pos.x + target_dx * 60.0
                            check_y = pos.y + target_dy * 60.0
                            future_biome = self.world_map.get_biome_at(check_x, check_y)
                            if not is_safe_biome(future_biome):
                                best_steer_x, best_steer_y = target_dx, target_dy
                                best_score = -9999.0
                                for i in range(16):
                                    angle = math.atan2(dy, dx) + (i - 8) * (math.pi / 8.0)
                                    sx = math.cos(angle)
                                    sy = math.sin(angle)
                                    tx = pos.x + sx * 50.0
                                    ty = pos.y + sy * 50.0
                                    tb = self.world_map.get_biome_at(tx, ty)
                                    if is_safe_biome(tb):
                                        dot_product = sx * target_dx + sy * target_dy
                                        if dot_product > best_score:
                                            best_score = dot_product
                                            best_steer_x, best_steer_y = sx, sy
                                best_dx, best_dy = best_steer_x, best_steer_y
                        pos.x += target_dx * speed * dt
                        pos.y += target_dy * speed * dt
                        action_taken = True

            if not action_taken:
                if effective_curiosity > 0.0:
                    pos.wander_timer -= dt
                    if pos.wander_timer <= 0:
                        pos.wander_angle = random.uniform(0, math.pi * 2)
                        pos.wander_timer = random.uniform(1.5, 5.0) * (1.0 - effective_curiosity * 0.5)
                    pos.x += math.cos(pos.wander_angle) * speed * dt
                    pos.y += math.sin(pos.wander_angle) * speed * dt
                
            new_biome = self.world_map.get_biome_at(pos.x, pos.y)
            in_danger_biome = not is_safe_biome(new_biome)
            if in_danger_biome:
                if effective_curiosity <= 0.3:
                    pos.x, pos.y = prev_x, prev_y
                    best_angle = pos.wander_angle + math.pi
                    for angle in [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]:
                        tx = pos.x + math.cos(angle) * 30
                        ty = pos.y + math.sin(angle) * 30
                        bt = self.world_map.get_biome_at(tx, ty)
                        if is_safe_biome(bt):
                            best_angle = angle; break
                    pos.wander_angle = best_angle
                    pos.blocked_timer = 1.0 + (getattr(dna, 'size_gene', 0.5) * 2.0)
                elif effective_curiosity <= 0.7:
                    escape_threshold = max(40.0, 100.0 - (effective_curiosity * 100))
                    if (health.breath / health.max_breath) * 100 <= escape_threshold:
                        pos.x, pos.y = prev_x, prev_y
                        best_angle = pos.wander_angle + math.pi
                        for angle in [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]:
                            tx = pos.x + math.cos(angle) * 30
                            ty = pos.y + math.sin(angle) * 30
                            bt = self.world_map.get_biome_at(tx, ty)
                            if is_safe_biome(bt):
                                best_angle = angle; break
                        pos.wander_angle = best_angle

            # 맵 바깥 경계선 강제 밀어내기 (보더 충돌)
            MARGIN = 30
            dx_dir = math.cos(pos.wander_angle)
            dy_dir = math.sin(pos.wander_angle)
            if pos.x < MARGIN:
                pos.x = MARGIN
                if dx_dir < 0:
                    pos.wander_angle = math.atan2(dy_dir, abs(dx_dir))
            if pos.x > self.width - MARGIN:
                pos.x = self.width - MARGIN
                if dx_dir > 0:
                    pos.wander_angle = math.atan2(dy_dir, -abs(dx_dir))
            if pos.y < MARGIN:
                pos.y = MARGIN
                if dy_dir < 0:
                    pos.wander_angle = math.atan2(abs(dy_dir), dx_dir)
            if pos.y > self.height - MARGIN:
                pos.y = self.height - MARGIN
                if dy_dir > 0:
                    pos.wander_angle = math.atan2(-abs(dy_dir), dx_dir)
            
            pos.x = max(MARGIN, min(self.width - MARGIN, pos.x))
            pos.y = max(MARGIN, min(self.height - MARGIN, pos.y))
            
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

            # 아종교배 판정
            p1_aquatic = getattr(dna1, 'aquatic_gene', 0.0) >= 0.5
            p2_aquatic = getattr(dna2, 'aquatic_gene', 0.0) >= 0.5
            is_crossbreed = (p1_aquatic != p2_aquatic)

            if is_crossbreed:
                if not self.enable_amphibians or random.random() < 0.5:
                    if self.logger:
                        self.logger.add_log(f"[유전사망] 아종 교배 유전 불일치 사망", entity_id=None, color=(255, 50, 50), x=new_x, y=new_y, is_aquatic=False)
                    if entity in self.world.entities:
                        self.world.entities.remove(entity)
                    continue
                force_amphibian = True
            else:
                force_amphibian = False

            child_aquatic = random.choice([getattr(dna1, 'aquatic_gene', 0.0), getattr(dna2, 'aquatic_gene', 0.0)]) >= 0.5
            biome_at_birth = self.world_map.get_biome_at(new_x, new_y)
            is_birth_water = biome_at_birth in (2, 4)
            if child_aquatic != is_birth_water:
                new_x, new_y = p_pos.x, p_pos.y
            
            gen1 = getattr(dna1, 'generation', 1)
            gen2 = getattr(dna2, 'generation', 1)
            new_gen = max(gen1, gen2) + 1

            # 유전 스탯 계산 및 돌연변이 적용
            mutation_chance = 0.15
            has_mutated = False
            final_mutated_features = {}
            
            def inherit_stat(p1_val, p2_val, stat_name):
                nonlocal has_mutated
                base_val = random.choice([p1_val, p2_val])
                if random.random() < mutation_chance:
                    has_mutated = True
                    is_macro = random.random() < 0.10
                    if is_macro:
                        mut_scale = random.choice([0.5, 2.0])
                        val = base_val * mut_scale
                        delta = f"*{mut_scale:.1f}"
                    else:
                        mut_delta = random.uniform(-0.15, 0.15)
                        val = base_val + mut_delta
                        delta = f"{'+' if mut_delta >= 0 else ''}{mut_delta:.2f}"
                    val = max(0.1, min(3.0, val))
                    final_mutated_features[stat_name] = delta
                    return val
                return base_val

            new_size = inherit_stat(dna1.size_gene, dna2.size_gene, "크기")
            new_speed = inherit_stat(dna1.speed_gene, dna2.speed_gene, "속도")
            new_meta = inherit_stat(dna1.metabolism_gene, dna2.metabolism_gene, "대사량")
            new_fur = inherit_stat(getattr(dna1, 'fur_gene', 0.5), getattr(dna2, 'fur_gene', 0.5), "털")
            new_aquatic = inherit_stat(getattr(dna1, 'aquatic_gene', 0.0), getattr(dna2, 'aquatic_gene', 0.0), "친수성")
            new_curiosity = inherit_stat(getattr(dna1, 'curiosity_gene', 0.5), getattr(dna2, 'curiosity_gene', 0.5), "호기심")

            child_is_mutated = has_mutated
            child_aquatic = new_aquatic >= 0.5
            
            # 색상 섞기
            c1 = dna1.color_gene
            c2 = dna2.color_gene
            new_color = (
                int((c1[0] + c2[0])/2 * random.uniform(0.9, 1.1)),
                int((c1[1] + c2[1])/2 * random.uniform(0.9, 1.1)),
                int((c1[2] + c2[2])/2 * random.uniform(0.9, 1.1))
            )
            new_color = (max(0, min(255, new_color[0])), max(0, min(255, new_color[1])), max(0, min(255, new_color[2])))
            
            # 대돌연변이 스펙 병사 판정
            macro_count = sum(1 for v in final_mutated_features.values() if '*' in v)
            if macro_count >= 2:
                disease_reason = "급격한 유전체 붕괴"
                if self.logger:
                    self.logger.add_log(f"[즉사] 대돌연변이 복수 유전병 즉사", entity_id=entity, color=(120, 120, 120), x=new_x, y=new_y, is_aquatic=child_aquatic)
                    self.logger.logs[-1]["dead_stat"] = {
                        "id": entity, "age": 0.0, "lifespan": 0.0, "max_health": 100.0, "max_energy": 100.0,
                        "size": new_size, "speed": new_speed, "meta": new_meta, "fur": new_fur, "aquatic": child_aquatic,
                        "curiosity": new_curiosity, "generation": new_gen, "is_mutated": True, "mutated_features": final_mutated_features,
                        "death_cause": f"유전병 즉사 ({disease_reason})"
                    }
                continue

            amphi_tag = " [양서류]" if force_amphibian else ""
            if self.logger:
                 biome_val = self.world_map.get_biome_at(new_x, new_y)
                 biome_name = {0: "초원", 1: "사막", 2: "바다", 3: "설원", 4: "깊은 물"}.get(biome_val, "미지")
                 mut_tag = " [돌연변이]" if child_is_mutated else ""
                 self.logger.add_log(f"[출산] ID:{p1_id} & {p2_id}의 자손 ID:{entity} ({new_gen}세대){mut_tag}{amphi_tag} ({biome_name})", entity_id=entity, color=(255, 105, 180), x=new_x, y=new_y, is_aquatic=child_aquatic)
                
            self.world.add_component(entity, PositionComponent(new_x, new_y))
            
            # 양서류 고유 유전 보정 (크기 0.61 이하 분산 유도)
            if force_amphibian:
                new_size = min(new_size * random.uniform(0.5, 0.75), 0.61)
                new_aquatic = random.uniform(0.35, 0.65)
                new_color = (60, 180, 160) # 청록색

            self.world.add_component(entity, DNAComponent(
                size_gene=new_size,
                speed_gene=new_speed,
                color_gene=new_color,
                metabolism_gene=new_meta,
                fur_gene=new_fur,
                aquatic_gene=new_aquatic,
                curiosity_gene=new_curiosity,
                generation=new_gen,
                is_mutated=child_is_mutated,
                mutated_features=final_mutated_features,
                is_amphibian=force_amphibian
            ))
            self.world.add_component(entity, RenderComponent(new_color, int(16 * new_size)))
            
            base_lifespan = random.uniform(150, 300)
            life_factor = max(0.5, min(3.0, (new_speed * 0.7 + new_size * 0.3) / 1.25))
            new_lifespan = base_lifespan / life_factor
            
            max_energy = 100.0
            self.world.add_component(entity, HealthComponent(
                current_health=30.0, max_health=100.0,
                age=0.0, lifespan=new_lifespan,
                energy=50.0, max_energy=max_energy,
                mating_cooldown=10.0
            ))


class MetabolismSystem:
    def __init__(self, world, world_map, logger=None):
        self.world = world
        self.world_map = world_map
        self.logger = logger
        self.death_markers = []

    def update(self, dt):
        entities = self.world.get_entities_with(HealthComponent, DNAComponent, PositionComponent)
        dead_entities = []
        for entity in entities:
            health = self.world.get_component(entity, HealthComponent)
            dna = self.world.get_component(entity, DNAComponent)
            pos = self.world.get_component(entity, PositionComponent)
            
            health.age += dt
            biome = self.world_map.get_biome_at(pos.x, pos.y)
            aquatic_gene = getattr(dna, 'aquatic_gene', 0.0)
            is_aquatic = aquatic_gene >= 0.5
            fur_gene = getattr(dna, 'fur_gene', 0.5)
            
            if _RUST_OK:
                new_breath, energy_drain, breath_damage = genesis_core.calc_metabolism(
                    biome, aquatic_gene, fur_gene,
                    dna.size_gene, dna.speed_gene, dna.metabolism_gene,
                    health.breath, health.max_breath, dt
                )
                health.breath = new_breath
                if breath_damage > 0:
                    health.current_health -= breath_damage
            else:
                is_in_water = biome in (2, 4)
                if aquatic_gene < 0.3 and biome == 4:
                    health.breath = 0.0
                elif (is_aquatic and not is_in_water) or (not is_aquatic and is_in_water):
                    health.breath = max(0.0, health.breath - 10 * dt)
                else:
                    health.breath = min(health.max_breath, health.breath + 15 * dt)
                if health.breath <= 0:
                    health.current_health -= 25 * dt
                drain_mult = 4.0
                energy_drain = ((dna.size_gene * 0.5 + dna.speed_gene * 1.5) * dna.metabolism_gene * drain_mult * dt) / 3.0
            
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
                self.death_markers.append({
                    'x': pos.x, 'y': pos.y, 'timer': 5.0,
                    'is_aquatic': aquatic_gene >= 0.5
                })
                dead_stat_data = {
                    "id": entity, "age": health.age, "lifespan": health.lifespan,
                    "max_health": health.max_health, "max_energy": health.max_energy,
                    "size": dna.size_gene, "speed": dna.speed_gene, "meta": dna.metabolism_gene,
                    "fur": getattr(dna, 'fur_gene', 0.5), "aquatic": aquatic_gene,
                    "curiosity": getattr(dna, 'curiosity_gene', 0.5), "generation": getattr(dna, 'generation', 1),
                    "is_mutated": getattr(dna, 'is_mutated', False),
                    "is_bird": getattr(dna, 'is_bird', False),
                    "is_egg": getattr(dna, 'is_egg', False),
                    "is_amphibian": getattr(dna, 'is_amphibian', False),
                    "death_cause": ""
                }
                if self.logger:
                    biome_val = self.world_map.get_biome_at(pos.x, pos.y)
                    biome_name = {0: "초원", 1: "사막", 2: "바다", 3: "설원", 4: "깊은 물"}.get(biome_val, "미지")
                    if health.breath <= 0:
                        cause = "질식사" if is_aquatic else "익사"
                        dead_stat_data["death_cause"] = cause
                        self.logger.add_log(f"[{cause}] ID:{entity} ({biome_name})", entity_id=entity, color=(100, 150, 255), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                    elif health.age > health.lifespan:
                        dead_stat_data["death_cause"] = "자연사"
                        self.logger.add_log(f"[자연사] ID:{entity} ({biome_name})", entity_id=entity, color=(100, 255, 100), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                    else:
                        dead_stat_data["death_cause"] = "아사"
                        self.logger.add_log(f"[아사] ID:{entity} ({biome_name})", entity_id=entity, color=(100, 255, 100), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                    self.logger.logs[-1]["dead_stat"] = dead_stat_data
                
        for entity in dead_entities:
            # 안전하게 삭제 시 에러 방어
            if entity in self.world.entities:
                self.world.entities.remove(entity)
            for comp_type in list(self.world.components.keys()):
                if entity in self.world.components[comp_type]:
                    del self.world.components[comp_type][entity]
                    
        for marker in list(self.death_markers):
            marker['timer'] -= dt
            if marker['timer'] <= 0:
                self.death_markers.remove(marker)


class RenderSystem:
    def __init__(self, world, screen, camera, world_width, world_height):
        self.world = world
        self.screen = screen
        self.camera = camera
        self.world_width = world_width
        self.world_height = world_height

    def update(self):
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
                    pygame.draw.circle(self.screen, render.color, (int(screen_x), int(screen_y)), max(2, screen_size // 2))
                    pygame.draw.circle(self.screen, (20, 80, 20), (int(screen_x), int(screen_y)), max(2, screen_size // 2), 1)
                else:
                    dna = self.world.get_component(entity, DNAComponent)
                    
                    # 알 렌더링
                    if dna and getattr(dna, 'is_egg', False):
                        r = max(4, screen_size)
                        egg_rect = pygame.Rect(int(screen_x - r * 0.7), int(screen_y - r), int(r * 1.4), int(r * 2))
                        pygame.draw.ellipse(self.screen, (240, 220, 180), egg_rect)
                        pygame.draw.ellipse(self.screen, (180, 150, 100), egg_rect, 1)
                    # 조류 세모 렌더링 (진행 각도 회전)
                    elif dna and getattr(dna, 'is_bird', False):
                        r = max(6, screen_size)
                        angle = getattr(pos, 'wander_angle', 0.0)
                        def rot(a):
                            return (int(screen_x + math.cos(angle + a) * r),
                                    int(screen_y + math.sin(angle + a) * r))
                        pts = [
                            rot(0),
                            rot(math.pi * 0.75),
                            rot(-math.pi * 0.75),
                        ]
                        pygame.draw.polygon(self.screen, render.color, pts)
                        pygame.draw.polygon(self.screen, (255, 220, 50), pts, 1)
                        h = self.world.get_component(entity, HealthComponent)
                        if h and h.energy < 80.0:
                            pygame.draw.polygon(self.screen, (255, 80, 80), pts, 2)
                    else:
                        pygame.draw.rect(self.screen, render.color, rect)
                        
                        if dna and hasattr(dna, 'fur_gene'):
                            fur_thickness = max(1, int((screen_size / 3) * dna.fur_gene))
                            if fur_thickness > 0 and dna.fur_gene > 0.1:
                                fur_color = (180, 180, 180)
                                pygame.draw.rect(self.screen, fur_color, rect, fur_thickness)
                        
                        # 양서류 청록색 아웃라인
                        if dna and getattr(dna, 'is_amphibian', False):
                            pygame.draw.rect(self.screen, (0, 220, 200), rect, 2)
                    
                    if self.camera.target_entity == entity:
                        pygame.draw.circle(self.screen, (255, 255, 0), (int(screen_x), int(screen_y)), max(3, screen_size//3))
