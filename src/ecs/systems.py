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
        
        # 러스트 가속 연산을 위한 식량 데이터 사전 가공 (매 프레임 1회만 수행)
        foods_data = []
        for food in foods:
            f_pos = self.world.get_component(food, PositionComponent)
            f_biome = self.world_map.get_biome_at(f_pos.x, f_pos.y)
            foods_data.append((food, f_pos.x, f_pos.y, f_biome))
        
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
            
            # 먹이 탐색 스캔 (러스트 가속 모듈 사용)
            nearest_food = None
            if health.energy < health.max_energy * 1.2:
                if _RUST_OK:
                    active_foods = [fd for fd in foods_data if fd[0] not in dead_foods]
                    nearest_food = genesis_core.find_nearest_food(
                        pos.x, pos.y,
                        is_aquatic, fur_gene, effective_curiosity,
                        active_foods,
                        lambda x, y: self.world_map.get_biome_at(x, y)
                    )
                else:
                    # 폴백: 순수 파이썬
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
                        # [우회 스티어링 시스템]
                        # 직선 경로 상에 위험 지형(물 등)이 감지되면, 주변 안전한 각도를 찾아 스티어링 조향 벡터를 꺾습니다.
                        target_dx = dx / length
                        target_dy = dy / length
                        
                        # 직선 60px 전방 예측 검사
                        check_x = pos.x + target_dx * 60.0
                        check_y = pos.y + target_dy * 60.0
                        future_biome = self.world_map.get_biome_at(check_x, check_y)
                        
                        # 안전하지 못한 지형이라면 우회 방향 탐색
                        if not is_safe_biome(future_biome):
                            best_steer_x, best_steer_y = target_dx, target_dy
                            best_score = -9999.0
                            # 주변 16방향 스캔하여 가장 안전하면서 목표와 가장 가까운 조향각 탐색
                            for i in range(16):
                                angle = math.atan2(dy, dx) + (i - 8) * (math.pi / 8.0)
                                sx = math.cos(angle)
                                sy = math.sin(angle)
                                # 50px 앞 지점 검증
                                tx = pos.x + sx * 50.0
                                ty = pos.y + sy * 50.0
                                tb = self.world_map.get_biome_at(tx, ty)
                                if is_safe_biome(tb):
                                    # 목표 방향과의 내적(유사도)을 계산하여 가장 최적의 육지 방향 채택
                                    dot_product = sx * target_dx + sy * target_dy
                                    if dot_product > best_score:
                                        best_score = dot_product
                                        best_steer_x, best_steer_y = sx, sy
                            target_dx, target_dy = best_steer_x, best_steer_y
                        
                        pos.x += target_dx * move_dist
                        pos.y += target_dy * move_dist
                action_taken = True

            # 3순위: 번식 (짝짓기) - 러스트 가속 탐색
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
                        candidates, list(mated_pairs),
                        lambda x, y: self.world_map.get_biome_at(x, y)
                    )
                    if res is not None:
                        nearest_mate = res[0]
                else:
                    # 폴백: 순수 파이썬
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
                        
                        # 번식 횟수 기록
                        health.mated_count = getattr(health, 'mated_count', 0) + 1
                        m_health.mated_count = getattr(m_health, 'mated_count', 0) + 1
                        
                        new_borns.append((pos, dna, m_dna, animal, nearest_mate))
                        
                        # 단회번식 판정: 번식 후 에너지가 0 이하가 된 경우 즉시 아사(탈진사/단회번식) 처리
                        if health.energy <= 0:
                            health.current_health = 0.0
                            if self.logger:
                                self.logger.add_log(f"[단회번식] ID:{animal} 최후의 번식 후 탈진 사망", entity_id=animal, color=(255, 105, 180), x=pos.x, y=pos.y, is_aquatic=is_aquatic)
                                self.logger.logs[-1]["dead_stat"] = {
                                    "id": animal,
                                    "age": health.age,
                                    "lifespan": health.lifespan,
                                    "max_health": health.max_health,
                                    "max_energy": health.max_energy,
                                    "size": dna.size_gene,
                                    "speed": dna.speed_gene,
                                    "meta": dna.metabolism_gene,
                                    "fur": getattr(dna, 'fur_gene', 0.5),
                                    "aquatic": getattr(dna, 'aquatic_gene', 0.0),
                                    "curiosity": getattr(dna, 'curiosity_gene', 0.5),
                                    "generation": getattr(dna, 'generation', 1),
                                    "is_mutated": getattr(dna, 'is_mutated', False),
                                    "death_cause": "단회번식 탈진사"
                                }
                        if m_health.energy <= 0:
                            m_health.current_health = 0.0
                            if self.logger:
                                m_dna = self.world.get_component(nearest_mate, DNAComponent)
                                m_aquatic = getattr(m_dna, 'aquatic_gene', 0.0) >= 0.5
                                self.logger.add_log(f"[단회번식] ID:{nearest_mate} 최후의 번식 후 탈진 사망", entity_id=nearest_mate, color=(255, 105, 180), x=m_pos.x, y=m_pos.y, is_aquatic=m_aquatic)
                                self.logger.logs[-1]["dead_stat"] = {
                                    "id": nearest_mate,
                                    "age": m_health.age,
                                    "lifespan": m_health.lifespan,
                                    "max_health": m_health.max_health,
                                    "max_energy": m_health.max_energy,
                                    "size": m_dna.size_gene,
                                    "speed": m_dna.speed_gene,
                                    "meta": m_dna.metabolism_gene,
                                    "fur": getattr(m_dna, 'fur_gene', 0.5),
                                    "aquatic": getattr(m_dna, 'aquatic_gene', 0.0),
                                    "curiosity": getattr(m_dna, 'curiosity_gene', 0.5),
                                    "generation": getattr(m_dna, 'generation', 1),
                                    "is_mutated": getattr(m_dna, 'is_mutated', False),
                                    "death_cause": "단회번식 탈진사"
                                }
                        action_taken = True
                    elif wants_to_mate or desperate_mating_mode:
                        target_dx = dx / length
                        target_dy = dy / length
                        
                        # desperate 모드가 아닐 때만 지형 우회 스티어링 적용
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
                                target_dx, target_dy = best_steer_x, best_steer_y
                        
                        pos.x += target_dx * speed * dt
                        pos.y += target_dy * speed * dt
                        
                        # desperate 모드가 아닐 때만 물 충돌 시 튕겨 나오기 처리
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
            child_aquatic = random.choice([getattr(dna1, 'aquatic_gene', 0.0), getattr(dna2, 'aquatic_gene', 0.0)]) >= 0.5
            biome_at_birth = self.world_map.get_biome_at(new_x, new_y)
            is_birth_water = biome_at_birth in (2, 4)
            if child_aquatic != is_birth_water:
                new_x, new_y = p_pos.x, p_pos.y
            
            # 세대 계산: max(부모1세대, 부모2세대) + 1
            gen1 = getattr(dna1, 'generation', 1)
            gen2 = getattr(dna2, 'generation', 1)
            new_gen = max(gen1, gen2) + 1

            has_mutated = False
            mutated_features = {} # {이름: 변화량_텍스트} 형식
            
            # 대돌연변이 판정 (10% 확률로 발생)
            # 대돌연변이가 당첨되면, 6가지 유전자 중 1~2개를 무작위로 선택하여 극단적인 변화를 줍니다.
            macro_targets = []
            if random.random() < 0.1:
                has_mutated = True
                possible_traits = ["크기", "속도", "대사량", "털", "친수성", "호기심"]
                macro_targets = random.sample(possible_traits, random.randint(1, 2))
            
            base_size = random.choice([dna1.size_gene, dna2.size_gene])
            base_speed = random.choice([dna1.speed_gene, dna2.speed_gene])
            base_meta = random.choice([dna1.metabolism_gene, dna2.metabolism_gene])
            base_color = random.choice([dna1.color_gene, dna2.color_gene])
            base_fur = random.choice([getattr(dna1, 'fur_gene', 0.5), getattr(dna2, 'fur_gene', 0.5)])
            base_aquatic = random.choice([getattr(dna1, 'aquatic_gene', 0.0), getattr(dna2, 'aquatic_gene', 0.0)])
            base_curiosity = random.choice([getattr(dna1, 'curiosity_gene', 0.5), getattr(dna2, 'curiosity_gene', 0.5)])

            # 1) 크기 유전자
            if "크기" in macro_targets:
                factor = random.uniform(0.5, 1.5)
                diff = factor - 1.0
                prefix = "+" if diff >= 0 else ""
                mutated_features["크기"] = f"{prefix}{diff*100:+.0f}%"
                new_size = base_size * factor
            else:
                new_size = base_size * random.uniform(0.85, 1.15)

            # 2) 속도 유전자
            if "속도" in macro_targets:
                factor = random.uniform(0.5, 1.5)
                diff = factor - 1.0
                prefix = "+" if diff >= 0 else ""
                mutated_features["속도"] = f"{prefix}{diff*100:+.0f}%"
                new_speed = base_speed * factor
            else:
                new_speed = base_speed * random.uniform(0.85, 1.15)

            # 3) 대사량 유전자
            if "대사량" in macro_targets:
                factor = random.uniform(0.5, 1.5)
                diff = factor - 1.0
                prefix = "+" if diff >= 0 else ""
                mutated_features["대사량"] = f"{prefix}{diff*100:+.0f}%"
                new_meta = base_meta * factor
            else:
                new_meta = base_meta * random.uniform(0.85, 1.15)
            
            # 4) 털 밀도 유전자
            if "털" in macro_targets:
                # 대돌연변이 시에는 크게 변동 (±0.4)
                fur_mutation = random.uniform(-0.4, 0.4)
                prefix = "+" if fur_mutation >= 0 else ""
                mutated_features["털"] = f"{prefix}{fur_mutation:+.2f}"
            else:
                # 일반 변이 (±0.15)
                fur_mutation = random.uniform(-0.15, 0.15)
            new_fur = max(0.0, min(1.0, base_fur + fur_mutation))
            
            # 5) 친수성 유전자
            if "친수성" in macro_targets:
                aq_mut = random.uniform(-0.35, 0.35)
                prefix = "+" if aq_mut >= 0 else ""
                mutated_features["친수성"] = f"{prefix}{aq_mut*100:+.0f}%"
                new_aquatic = max(0.0, min(1.0, base_aquatic + aq_mut))
            else:
                aq_mut = random.uniform(-0.1, 0.1) if random.random() < 0.2 else 0.0
                new_aquatic = max(0.0, min(1.0, base_aquatic + aq_mut))
            
            # 6) 호기심 유전자
            if "호기심" in macro_targets:
                cur_mut = random.uniform(-0.35, 0.35)
                prefix = "+" if cur_mut >= 0 else ""
                mutated_features["호기심"] = f"{prefix}{cur_mut*100:+.0f}%"
                new_curiosity = max(0.0, min(1.0, base_curiosity + cur_mut))
            else:
                cur_mut = random.uniform(-0.1, 0.1) if random.random() < 0.2 else 0.0
                new_curiosity = max(0.0, min(1.0, base_curiosity + cur_mut))
            
            r, g, b = base_color
            new_r = max(0, min(255, r + random.randint(-15, 15)))
            new_g = max(0, min(255, g + random.randint(-15, 15)))
            new_b = max(0, min(255, b + random.randint(-15, 15)))
            new_color = (new_r, new_g, new_b)
            
            # 부모의 돌연변이 상태 획득
            p1_is_mut = getattr(dna1, 'is_mutated', False)
            p2_is_mut = getattr(dna2, 'is_mutated', False)
            
            # 부모로부터 돌연변이 상태가 상속될지 결정 (20% 확률)
            parent_mut_inherited = False
            if p1_is_mut or p2_is_mut:
                if random.random() < 0.2:
                    parent_mut_inherited = True
            
            # 최종 자손 돌연변이 판정: 이번에 돌연변이가 발생했거나, 부모의 돌연변이가 상속된 경우
            child_is_mutated = has_mutated or parent_mut_inherited
            
            # 부모의 돌연변이 특징 상속
            inherited_features = {}
            if parent_mut_inherited:
                # 부모 특징 딕셔너리 병합
                p1_feats = getattr(dna1, 'mutated_features', {})
                p2_feats = getattr(dna2, 'mutated_features', {})
                if isinstance(p1_feats, dict):
                    inherited_features.update(p1_feats)
                if isinstance(p2_feats, dict):
                    inherited_features.update(p2_feats)
            
            final_mutated_features = {}
            final_mutated_features.update(inherited_features)
            final_mutated_features.update(mutated_features)
            
            # 유전병 판정:
            # 1. 부모 둘 다 돌연변이 세대(is_mutated==True)인 경우
            # 2. 한쪽 부모만 돌연변이인데 자식 개체도 돌연변이(has_mutated==True)가 발생한 경우
            is_genetic_disease_death = False
            disease_reason = ""
            if p1_is_mut and p2_is_mut:
                is_genetic_disease_death = True
                disease_reason = "돌연변이간 교배"
            elif (p1_is_mut or p2_is_mut) and has_mutated:
                is_genetic_disease_death = True
                disease_reason = "돌연변이유전+추가변이"
            
            if is_genetic_disease_death:
                if self.logger:
                    disease_msg = f"[유전사망] ID:{entity} ({disease_reason}, 크기:{new_size:.1f}/속도:{new_speed:.1f}/세대:{new_gen})"
                    self.logger.add_log(
                        disease_msg,
                        entity_id=None,
                        color=(255, 50, 50),
                        x=new_x,
                        y=new_y,
                        is_aquatic=child_aquatic
                    )
                    self.logger.logs[-1]["dead_stat"] = {
                        "id": entity,
                        "age": 0.0,
                        "lifespan": 0.0,
                        "max_health": 100.0,
                        "max_energy": 100.0,
                        "size": new_size,
                        "speed": new_speed,
                        "meta": new_meta,
                        "fur": new_fur,
                        "aquatic": child_aquatic,
                        "curiosity": new_curiosity,
                        "generation": new_gen,
                        "is_mutated": True,
                        "mutated_features": final_mutated_features,
                        "death_cause": f"유전병 즉사 ({disease_reason})"
                    }
                continue

            # 출산 성공 로그
            if self.logger:
                 biome_val = self.world_map.get_biome_at(new_x, new_y)
                 biome_name = {0: "초원", 1: "사막", 2: "바다", 3: "설원", 4: "깊은 물"}.get(biome_val, "미지")
                 mut_tag = " [돌연변이]" if has_mutated else ""
                 self.logger.add_log(f"[출산] ID:{p1_id} & {p2_id}의 자손 ID:{entity} ({new_gen}세대){mut_tag} ({biome_name})", entity_id=entity, color=(255, 105, 180), x=new_x, y=new_y, is_aquatic=child_aquatic)
                
            self.world.add_component(entity, PositionComponent(new_x, new_y))
            
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
                mutated_features=final_mutated_features
            ))
            self.world.add_component(entity, RenderComponent(new_color, int(16 * new_size)))
            
            # Live Fast Die Young
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
                # 러스트 calc_metabolism 으로 호흡 및 기력 소모 일괄 계산
                new_breath, energy_drain, breath_damage = genesis_core.calc_metabolism(
                    biome, aquatic_gene, fur_gene,
                    dna.size_gene, dna.speed_gene, dna.metabolism_gene,
                    health.breath, health.max_breath, dt
                )
                health.breath = new_breath
                if breath_damage > 0:
                    health.current_health -= breath_damage
            else:
                # 폴백: 순수 파이썬 호흡 처리
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
                # 사망 위치 마커 추가 (x, y, 타이머, 수생성 여부)
                self.death_markers.append({
                    'x': pos.x,
                    'y': pos.y,
                    'timer': 5.0, # 5초간 맵에 표시
                    'is_aquatic': aquatic_gene >= 0.5
                })
                # 생명체의 현재 스펙 캡처 (사망 후 인스펙션용)
                dead_stat_data = {
                    "id": entity,
                    "age": health.age,
                    "lifespan": health.lifespan,
                    "max_health": health.max_health,
                    "max_energy": health.max_energy,
                    "size": dna.size_gene,
                    "speed": dna.speed_gene,
                    "meta": dna.metabolism_gene,
                    "fur": getattr(dna, 'fur_gene', 0.5),
                    "aquatic": aquatic_gene,
                    "curiosity": getattr(dna, 'curiosity_gene', 0.5),
                    "generation": getattr(dna, 'generation', 1),
                    "is_mutated": getattr(dna, 'is_mutated', False),
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
                    # 가장 최근에 추가된 로그 엔트리에 dead_stat 데이터 매핑
                    self.logger.logs[-1]["dead_stat"] = dead_stat_data
                
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
