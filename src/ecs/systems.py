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
                
            # 기본 시야 300, 배고플 때는 필사적으로 시야를 600까지 확장
            sensor_radius = 300.0
            if health.energy < health.max_energy * 0.5:
                sensor_radius = 600.0
            speed = 50 * dna.speed_gene
            aquatic_gene = getattr(dna, 'aquatic_gene', 0.0)
            curiosity = getattr(dna, 'curiosity_gene', 0.5)
            is_aquatic = aquatic_gene >= 0.5
            fur_gene = getattr(dna, 'fur_gene', 0.5)
            
            # 개체 맞춤형 지형 안전성 검사 함수 (수생성 및 털 밀도 기준)
            def is_safe_biome(b_val):
                # 1) 물/육지 적합성
                if is_aquatic:
                    if b_val not in (2, 4): return False
                else:
                    if b_val in (2, 4): return False
                # 2) 털 밀도에 따른 기온 적합성 (사막/설원)
                if b_val == 1 and fur_gene > 0.2: # 사막인데 털이 너무 두꺼우면 부적합
                    return False
                if b_val == 3 and fur_gene < 0.8: # 설원인데 털이 너무 얇으면 부적합
                    return False
                return True
            
            # 지형 속도 패널티 적용
            current_biome = self.world_map.get_biome_at(pos.x, pos.y)
            if current_biome == 1: # DESERT
                fur_gene = getattr(dna, 'fur_gene', 0.5)
                if fur_gene > 0.2:
                    speed *= (0.5 + 0.5 * (1.0 - fur_gene))
            elif current_biome == 3: # SNOW
                fur_gene = getattr(dna, 'fur_gene', 0.5)
                if fur_gene < 0.8:
                    speed *= (0.5 + 0.5 * fur_gene)

            # --- 1순위: 생존 본능 (호흡 40% 이하 시 100% 찰 때까지 탈출 유지 락) ---
            is_escaping_breath = getattr(health, 'is_escaping_breath', False)
            if health.breath <= health.max_breath * 0.4:
                health.is_escaping_breath = True
                is_escaping_breath = True
            elif is_escaping_breath and health.breath >= health.max_breath:
                health.is_escaping_breath = False
                is_escaping_breath = False
            
            survival_escape = is_escaping_breath

            wants_to_mate = (health.energy >= health.max_energy * 1.0 and health.age > 20.0 and health.mating_cooldown <= 0)
            
            prev_x, prev_y = pos.x, pos.y
            
            if pos.blocked_timer > 0:
                pos.blocked_timer -= dt

            # 수명 기반 나이 비율 계산
            life_pct = health.age / max(health.lifespan, 1.0)
            
            # 실질적 호기심: 60% 전 = 최대, 60~80% = 선형 감소, 80%+ = 0 (최솟값 5% 보정)
            if life_pct < 0.6:
                effective_curiosity = curiosity
            elif life_pct < 0.8:
                effective_curiosity = curiosity * (1.0 - (life_pct - 0.6) / 0.2)
            else:
                effective_curiosity = 0.0
            
            # 호기심 최솟값은 5% (0.05)로 고정 (노년기도 최소한의 움직임 보장)
            effective_curiosity = max(0.05, effective_curiosity)
            
            # 최후의 번식 본능 (복상사 모드) 발동 조건:
            # 수명 90% 이상 소진 (life_pct >= 0.9) AND 번식 횟수 0회 (health.mated_count == 0)
            desperate_mating_mode = (life_pct >= 0.9 and getattr(health, 'mated_count', 0) == 0)
            
            # 짝짓기를 적극적으로 찾는 조건: 수명 60%+ AND 기력 충분 AND 쿨다운 없음
            wants_to_mate = (life_pct >= 0.6 and health.energy >= health.max_energy * 0.7 and health.mating_cooldown <= 0)
            # 우연한 만남 번식 조건: 쿨다운만 없으면 언제든 가능
            can_mate_opportunistic = (health.mating_cooldown <= 0 and health.energy >= health.max_energy * 0.5)

            # 최후의 번식 본능이 켜진 개체는 생존 본능(도망)을 완전히 무시
            if survival_escape and not desperate_mating_mode:
                # 안전지대에 이미 도달해 있다면 움직이지 않고 제자리에서 완전히 숨을 고릅니다.
                current_biome = self.world_map.get_biome_at(pos.x, pos.y)
                if is_safe_biome(current_biome):
                    continue
                
                # 안전 지형으로 도망 (아드레날린: 속도 1.2배)
                speed *= 1.2
                best_angle = None
                # 시야 범위를 단계적으로 넓히며 안전지대 탐색 (40px -> 120px -> 250px -> 450px)
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
                # 사방이 위험 지형(섬 고립 등)이면 물이라도 들어가서 탈출 시도
                if best_angle is None:
                    best_angle = random.uniform(0, math.pi * 2)
                target_angle = best_angle
                angle_diff = (target_angle - pos.wander_angle + math.pi) % (2 * math.pi) - math.pi
                pos.wander_angle += angle_diff * 8.0 * dt
                pos.x += math.cos(pos.wander_angle) * speed * dt
                pos.y += math.sin(pos.wander_angle) * speed * dt
                # 보더 클램프
                MARGIN = 30
                dx_dir = math.cos(pos.wander_angle)
                dy_dir = math.sin(pos.wander_angle)
                if pos.x < MARGIN and dx_dir < 0: pos.wander_angle = math.atan2(dy_dir, abs(dx_dir))
                if pos.x > self.width - MARGIN and dx_dir > 0: pos.wander_angle = math.atan2(dy_dir, -abs(dx_dir))
                if pos.y < MARGIN and dy_dir < 0: pos.wander_angle = math.atan2(abs(dy_dir), dx_dir)
                if pos.y > self.height - MARGIN and dy_dir > 0: pos.wander_angle = math.atan2(-abs(dy_dir), dx_dir)
                pos.x = max(0, min(self.width, pos.x))
                pos.y = max(0, min(self.height, pos.y))
                continue
            
            # 배고픔 상태 판별 (80% 미만이면 확실히 배고픔)
            is_hungry = (health.energy < health.max_energy * 0.8)
            
            # 먹이 탐색 스캔 (맵 전범위 스캔 및 호기심에 따른 필터링)
            nearest_food = None
            min_food_dist_sq = float('inf')
            if health.energy < health.max_energy * 1.2:
                for food in foods:
                    if food in dead_foods: continue
                    f_pos = self.world.get_component(food, PositionComponent)
                    
                    # 1) 제곱 거리로 가장 가까운 후보인지 빠르게 사전 스캔 (연산 최적화)
                    dx = pos.x - f_pos.x
                    dy = pos.y - f_pos.y
                    dist_sq = dx*dx + dy*dy
                    if dist_sq >= min_food_dist_sq:
                        continue
                        
                    # 2) 호기심에 따른 지형 적합성 조건 필터링
                    food_biome = self.world_map.get_biome_at(f_pos.x, f_pos.y)
                    
                    # [호기심 70% 미만] 바다 혹은 육지 반대편 매체에 있는 밥은 인식 불가
                    if effective_curiosity < 0.7:
                        if is_aquatic != (food_biome in (2, 4)):
                            continue
                            
                    # [호기심 40% 미만] 자신이 살기 좋은 기후 지역(털 적합성)에 있는 밥만 추적
                    if effective_curiosity < 0.4:
                        if food_biome == 1 and fur_gene > 0.2: # 사막인데 털 많으면 제외
                            continue
                        if food_biome == 3 and fur_gene < 0.8: # 설원인데 털 적으면 제외
                            continue
                            
                    # 3) 경로 상의 위험 지형 검사 (레이캐스팅 4단계) - 본인의 호기심 수준에 맞춘 경로 확인
                    path_safe = True
                    steps = 4
                    for step in range(1, steps):
                        tx = pos.x + (f_pos.x - pos.x) * (step / steps)
                        ty = pos.y + (f_pos.y - pos.y) * (step / steps)
                        tb = self.world_map.get_biome_at(tx, ty)
                        
                        # 호기심 70% 미만은 수생/육지 매체 경계 돌파 경로 금지
                        if effective_curiosity < 0.7:
                            if is_aquatic != (tb in (2, 4)):
                                path_safe = False
                                break
                        # 호기심 40% 미만은 부적합 기후 지형 경로 금지
                        if effective_curiosity < 0.4:
                            if tb == 1 and fur_gene > 0.2:
                                path_safe = False
                                break
                            if tb == 3 and fur_gene < 0.8:
                                path_safe = False
                                break
                                
                    if not path_safe:
                        continue
                        
                    # 4) 모든 필터를 통과하고 더 가까운 식량이므로 대상 갱신
                    min_food_dist_sq = dist_sq
                    nearest_food = food

            action_taken = False

            # 2순위: 배고픔 (식욕) - 아주 배고프면(is_hungry) 짝짓기보다 밥 찾기가 우선
            # 단, 최후의 번식 본능(desperate_mating_mode)이 발동한 경우 식욕을 무시하고 바로 번식 시도
            if is_hungry and nearest_food is not None and not desperate_mating_mode:
                f_pos = self.world.get_component(nearest_food, PositionComponent)
                dx = f_pos.x - pos.x
                dy = f_pos.y - pos.y
                length = math.hypot(dx, dy)
                render_comp = self.world.get_component(animal, RenderComponent)
                # 판정이 너무 구려 아사하는 것을 방지하기 위해 최소 20px 보정 및 크기 대비 1.2배 확장 적용
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
                        pos.x += (dx / length) * move_dist
                        pos.y += (dy / length) * move_dist
                action_taken = True

            # 3순위: 번식 (짝짓기)
            if not action_taken and len(animals) + len(new_borns) < self.max_population:
                # desperate 모드인 경우 맵 전체 시야(self.width * 2)로 짝을 강제 탐색
                scan_radius = self.width * 2 if desperate_mating_mode else (sensor_radius if wants_to_mate else 15.0)
                nearest_mate = None
                min_mate_dist = float('inf')
                
                for other in animals:
                    if other == animal or other in mated_pairs: continue
                    o_pos = self.world.get_component(other, PositionComponent)
                    
                    # 1) x, y 좌표 차이가 시야 범위를 벗어나면 제외 (빠른 필터링) - desperate 모드인 경우 필터링 생략
                    if not desperate_mating_mode:
                        if abs(pos.x - o_pos.x) > scan_radius or abs(pos.y - o_pos.y) > scan_radius:
                            continue
                        
                    # 2) 짝의 위치가 나에게 안전한 지형인지 검증 - desperate 모드인 경우 지형 제약 무시
                    if not desperate_mating_mode:
                        mate_biome = self.world_map.get_biome_at(o_pos.x, o_pos.y)
                        if not is_safe_biome(mate_biome):
                            continue
                        
                    # 3) 가는 경로 상에 위험 지형이 있는지 검사 (직선 경로 레이캐스팅 4단계) - desperate 모드인 경우 무시
                    if not desperate_mating_mode:
                        path_safe = True
                        steps = 4
                        for step in range(1, steps):
                            tx = pos.x + (o_pos.x - pos.x) * (step / steps)
                            ty = pos.y + (o_pos.y - pos.y) * (step / steps)
                            if not is_safe_biome(self.world_map.get_biome_at(tx, ty)):
                                path_safe = False
                                break
                        if not path_safe:
                            continue
                        
                    other_health = self.world.get_component(other, HealthComponent)
                    # 짝이 번식 가능한지 검증 (desperate 모드이면 짝의 기력 요구사항을 30% 이상으로 완화)
                    mate_req_energy = other_health.max_energy * 0.3 if desperate_mating_mode else other_health.max_energy * 0.5
                    other_can_mate = (other_health.mating_cooldown <= 0 and other_health.energy >= mate_req_energy)
                    if other_can_mate:
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
                        
                        # 번식 횟수 기록
                        health.mated_count = getattr(health, 'mated_count', 0) + 1
                        m_health.mated_count = getattr(m_health, 'mated_count', 0) + 1
                        
                        new_borns.append((pos, dna, m_dna, animal, nearest_mate))
                        
                        # 단회번식 판정: 번식 후 에너지가 0 이하가 된 경우 즉시 아사(탈진사/단회번식) 처리
                        if health.energy <= 0:
                            health.current_health = 0.0
                            if self.logger:
                                self.logger.add_log(f"[단회번식] ID:{animal} 최후의 번식 후 탈진 사망", entity_id=animal, color=(255, 105, 180), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                        if m_health.energy <= 0:
                            m_health.current_health = 0.0
                            if self.logger:
                                m_dna = self.world.get_component(nearest_mate, DNAComponent)
                                m_aquatic = getattr(m_dna, 'aquatic_gene', 0.0) >= 0.5
                                self.logger.add_log(f"[단회번식] ID:{nearest_mate} 최후의 번식 후 탈진 사망", entity_id=nearest_mate, color=(255, 105, 180), x=m_pos.x, y=m_pos.y, is_aquatic=m_aquatic)
                        action_taken = True
                    elif wants_to_mate or desperate_mating_mode:
                        pos.x += (dx / length) * speed * dt
                        pos.y += (dy / length) * speed * dt
                        
                        # desperate 모드가 아닐 때만 물 충돌 시 튕겨 나오기 처리 (desperate 모드는 육지/바다 경계 돌파 직진)
                        if not desperate_mating_mode and self.world_map.get_biome_at(pos.x, pos.y) in (2, 4):
                            pos.x, pos.y = prev_x, prev_y
                            best_angle = pos.wander_angle + math.pi
                            for angle in [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]:
                                tx = pos.x + math.cos(angle) * 30
                                ty = pos.y + math.sin(angle) * 30
                                if self.world_map.get_biome_at(tx, ty) not in (2, 4):
                                    best_angle = angle; break
                            pos.wander_angle = best_angle
                            pos.blocked_timer = 1.0 + (getattr(dna, 'size_gene', 0.5) * 2.0)
                        action_taken = True

            # 4순위: 배고프지는 않은데 짝도 시야에 없어서 밥이라도 먹는 경우 (덜 배고픈 상태의 차선책) -> 삭제됨

            # 5순위: 호기심 (탐험) - 밥도 없고 짝도 없을 때
            if not action_taken:
                if effective_curiosity > 0.0:
                    pos.wander_timer -= dt
                    if pos.wander_timer <= 0:
                        pos.wander_angle = random.uniform(0, math.pi * 2)
                        pos.wander_timer = random.uniform(1.5, 5.0) * (1.0 - effective_curiosity * 0.5)
                    pos.x += math.cos(pos.wander_angle) * speed * dt
                    pos.y += math.sin(pos.wander_angle) * speed * dt
                
            # 물 및 기온 차단 (호기심 제외하고 부적합 지형 진입 차단)
            new_biome = self.world_map.get_biome_at(pos.x, pos.y)
            in_danger_biome = not is_safe_biome(new_biome)
            
            if in_danger_biome:
                # effective_curiosity 기반 진입 결정
                if effective_curiosity <= 0.3:
                    # 겁쟁이 or 노년: 즉시 차단 후 즉각 방향 반전 (경계에서 비비적대지 않고 바로 돌도록 즉시 각도 대입)
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
                # 호기심 31~70%: 진입은 허용하되 호흡 역치 도달 시 탈출
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
                # 호기심 71%+: 자유롭게 진입 (호흡이 40%되면 생존본능이 처리)

            # 보더 안전마진: 벽 30px 이내에서 벽 방향으로 가려 하면 꺾음
            MARGIN = 30
            dx_dir = math.cos(pos.wander_angle)
            dy_dir = math.sin(pos.wander_angle)
            if pos.x < MARGIN and dx_dir < 0: dx_dir = abs(dx_dir); pos.wander_angle = math.atan2(dy_dir, dx_dir)
            if pos.x > self.width - MARGIN and dx_dir > 0: dx_dir = -abs(dx_dir); pos.wander_angle = math.atan2(dy_dir, dx_dir)
            if pos.y < MARGIN and dy_dir < 0: dy_dir = abs(dy_dir); pos.wander_angle = math.atan2(dy_dir, dx_dir)
            if pos.y > self.height - MARGIN and dy_dir > 0: dy_dir = -abs(dy_dir); pos.wander_angle = math.atan2(dy_dir, dx_dir)
            
            pos.x = max(0, min(self.width, pos.x))
            pos.y = max(0, min(self.height, pos.y))
            
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
            # 자손이 수생 생물인지 여부 (부모 유전자 기반 예측)
            child_aquatic = random.choice([getattr(dna1, 'aquatic_gene', 0.0), getattr(dna2, 'aquatic_gene', 0.0)]) >= 0.5
            biome_at_birth = self.world_map.get_biome_at(new_x, new_y)
            is_birth_water = biome_at_birth in (2, 4)
            
            # 수생성과 지형이 불일치하는 오프셋 스폰 시 부모의 원 위치로 복귀
            if child_aquatic != is_birth_water:
                new_x, new_y = p_pos.x, p_pos.y
                
            if self.logger:
                 biome_val = self.world_map.get_biome_at(new_x, new_y)
                 biome_name = {0: "초원", 1: "사막", 2: "바다", 3: "설원", 4: "깊은 물"}.get(biome_val, "미지")
                 self.logger.add_log(f"[출산] ID:{p1_id} & {p2_id}의 자손 ID:{entity} ({biome_name})", entity_id=entity, color=(255, 105, 180), x=new_x, y=new_y, is_aquatic=child_aquatic)
                
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
            base_aquatic = random.choice([getattr(dna1, 'aquatic_gene', 0.0), getattr(dna2, 'aquatic_gene', 0.0)])
            base_curiosity = random.choice([getattr(dna1, 'curiosity_gene', 0.5), getattr(dna2, 'curiosity_gene', 0.5)])
            
            new_size = mutate(base_size)
            new_speed = mutate(base_speed)
            new_meta = mutate(base_meta)
            
            # 털 밀도는 0.0 ~ 1.0 사이이므로 덧셈/뺄셈 방식의 돌연변이 적용 (최대 ±0.25)
            fur_mutation = random.uniform(-0.25, 0.25)
            new_fur = max(0.0, min(1.0, base_fur + fur_mutation))
            
            # 친수성 및 호기심 유전자 돌연변이 적용 (최대 ±0.15)
            aquatic_mutation = random.uniform(-0.15, 0.15) if random.random() < 0.2 else 0.0
            new_aquatic = max(0.0, min(1.0, base_aquatic + aquatic_mutation))
            
            curiosity_mutation = random.uniform(-0.15, 0.15) if random.random() < 0.2 else 0.0
            new_curiosity = max(0.0, min(1.0, base_curiosity + curiosity_mutation))
            
            r, g, b = base_color
            new_r = max(0, min(255, r + random.randint(-15, 15)))
            new_g = max(0, min(255, g + random.randint(-15, 15)))
            new_b = max(0, min(255, b + random.randint(-15, 15)))
            new_color = (new_r, new_g, new_b)
            
            self.world.add_component(entity, DNAComponent(
                size_gene=new_size,
                speed_gene=new_speed,
                color_gene=new_color,
                metabolism_gene=new_meta,
                fur_gene=new_fur,
                aquatic_gene=new_aquatic,
                curiosity_gene=new_curiosity
            ))
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
        self.death_markers = []

    def update(self, dt):
        entities = self.world.get_entities_with(HealthComponent, DNAComponent, PositionComponent)
        dead_entities = []
        for entity in entities:
            health = self.world.get_component(entity, HealthComponent)
            dna = self.world.get_component(entity, DNAComponent)
            pos = self.world.get_component(entity, PositionComponent)
            
            health.age += dt
            
            # --- 1. 호흡(Breath) 처리 ---
            biome = self.world_map.get_biome_at(pos.x, pos.y)
            aquatic_gene = getattr(dna, 'aquatic_gene', 0.0)
            is_aquatic = aquatic_gene >= 0.5
            is_in_water = biome in (2, 4)
            
            # 친수성 30% 미만이 깊은 물 진입 시 즉시 익사
            if aquatic_gene < 0.3 and biome == 4:
                health.breath = 0.0
            elif (is_aquatic and not is_in_water) or (not is_aquatic and is_in_water):
                health.breath -= 10 * dt
            else:
                health.breath += 15 * dt
            health.breath = max(0.0, min(health.max_breath, health.breath))
            
            if health.breath <= 0:
                health.current_health -= 25 * dt

            # --- 2. 털 마스터리 및 기력 소모 ---
            drain_mult = 4.0
            fur_gene = getattr(dna, 'fur_gene', 0.5)
            
            if biome == 1: # DESERT
                if fur_gene <= 0.05:
                    drain_mult = 2.0   # 사막 마스터: 절반
                elif fur_gene <= 0.2:
                    drain_mult = 4.0   # 사막 면역: 기본
                else:
                    drain_mult = 4.0 + (fur_gene * 16.0)
            elif biome == 3: # SNOW
                if fur_gene >= 0.95:
                    drain_mult = 2.0   # 설원 마스터: 절반
                elif fur_gene >= 0.8:
                    drain_mult = 4.0   # 설원 면역: 기본
                else:
                    drain_mult = 4.0 + ((1.0 - fur_gene) * 16.0)
            
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
                # 사망 위치 마커 추가 (x, y, 타이머, 수생성 여부)
                self.death_markers.append({
                    'x': pos.x,
                    'y': pos.y,
                    'timer': 5.0, # 5초간 맵에 표시
                    'is_aquatic': aquatic_gene >= 0.5
                })
                if self.logger:
                    biome_val = self.world_map.get_biome_at(pos.x, pos.y)
                    biome_name = {0: "초원", 1: "사막", 2: "바다", 3: "설원", 4: "깊은 물"}.get(biome_val, "미지")
                    if health.breath <= 0:
                        cause = "질식사" if is_aquatic else "익사"
                        self.logger.add_log(f"[{cause}] ID:{entity} ({biome_name})", entity_id=entity, color=(100, 150, 255), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                    elif health.age > health.lifespan:
                        self.logger.add_log(f"[자연사] ID:{entity} ({biome_name})", entity_id=entity, color=(100, 255, 100), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                    else:
                        self.logger.add_log(f"[아사] ID:{entity} ({biome_name})", entity_id=entity, color=(100, 255, 100), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                
        for entity in dead_entities:
            self.world.entities.remove(entity)
            for comp_type in list(self.world.components.keys()):
                if entity in self.world.components[comp_type]:
                    del self.world.components[comp_type][entity]
                    
        # 사망 마커 타이머 업데이트
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
