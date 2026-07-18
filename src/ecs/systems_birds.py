"""
조류(새) 및 알(Egg) 시스템
- BirdSystem: 조류 행동 (산책, 비행 사냥, 단회 번식), 알 부화 처리
- 조류는 독립 종이므로 SurvivalSystem과 분리하여 처리
"""
import math
import random
import pygame
from ecs.components import (PositionComponent, RenderComponent, DNAComponent,
                             HealthComponent, FoodComponent)

try:
    import genesis_core
    _RUST_OK = True
except ImportError:
    _RUST_OK = False


BIRD_FLIGHT_SPEED   = 12 * 50   # 비행 속도 픽셀/초 (속도 12 스케일)
BIRD_APPROACH_SPEED = 80         # 사냥 근접 속도: 먹이 60px 이내에서 감속
BIRD_WALK_SPEED     = 35         # 산책 속도 픽셀/초 (느리게 걸음)
BIRD_ENERGY_HUNT    = 80.0       # 이 값 미만이면 비행 사냥 시작
BIRD_ENERGY_FULL    = 160.0      # 사냥 후 최대 에너지
BIRD_MATE_MIN_ENERGY = 120.0     # 교배 가능 최소 에너지
BIRD_MATE_COST      = 80.0       # 교배 시 에너지 소모
BIRD_EGG_HATCH_TIME = 30.0       # 알 부화 시간(초)
BIRD_PREY_MAX_SIZE  = 0.60       # 조류의 사냥 가능 최대 크기
BIRD_WALK_DRAIN     = 0.3        # 산책 시 초당 에너지 소모
BIRD_FLIGHT_DRAIN_MULT = 1.5     # 비행 시 에너지 소모 배율
BIRD_CATCH_RADIUS   = 30.0       # 포식 판정 반경 (크게 해서 빠른 속도에도 안정적 포식)
BIRD_SLOW_RADIUS    = 60.0       # 이 거리 이내에서 감속 시작

# 조류 삼각형 렌더링 색상
BIRD_COLOR = (220, 180, 80)  # 황금빛 갈색
EGG_COLOR  = (240, 220, 180) # 크림색
EGG_SIZE   = 5


class BirdSystem:
    def __init__(self, world, world_map, world_width, world_height, logger=None):
        self.world = world
        self.world_map = world_map
        self.width = world_width
        self.height = world_height
        self.logger = logger

    # ---------------------------------------------------------------
    def update(self, dt):
        self._update_eggs(dt)
        self._update_birds(dt)

    # ---------------------------------------------------------------
    def _update_eggs(self, dt):
        """알 부화 처리"""
        eggs = [e for e in self.world.entities
                if self._get(e, DNAComponent) and self._get(e, DNAComponent).is_egg]
        hatched = []
        for egg in eggs:
            dna = self._get(egg, DNAComponent)
            dna.egg_timer += dt
            if dna.egg_timer >= BIRD_EGG_HATCH_TIME:
                hatched.append(egg)

        for egg in hatched:
            pos = self._get(egg, PositionComponent)
            dna = self._get(egg, DNAComponent)
            if pos is None or dna is None:
                continue
            # 알 → 새 개체로 전환
            new_bird = self.world.create_entity()
            new_dna = DNAComponent(
                size_gene=dna.size_gene,
                speed_gene=dna.speed_gene,
                color_gene=BIRD_COLOR,
                metabolism_gene=dna.metabolism_gene,
                fur_gene=0.5,
                aquatic_gene=0.0,
                curiosity_gene=0.0,
                generation=dna.generation,
                is_bird=True,
                is_egg=False,
            )
            self.world.add_component(new_bird, PositionComponent(pos.x + random.uniform(-10, 10),
                                                                  pos.y + random.uniform(-10, 10)))
            self.world.add_component(new_bird, new_dna)
            self.world.add_component(new_bird, RenderComponent(BIRD_COLOR, 10))
            lifespan = random.uniform(300, 600)  # 수명 2배
            self.world.add_component(new_bird, HealthComponent(
                current_health=100.0, max_health=100.0,
                age=0.0, lifespan=lifespan,
                energy=80.0, max_energy=160.0,
                mating_cooldown=20.0
            ))
            if self.logger:
                self.logger.add_log(f"[부화] 알이 부화! 새 ID:{new_bird}", color=(255, 230, 100),
                                    x=pos.x, y=pos.y, is_aquatic=False)
            self._remove_entity(egg)

    # ---------------------------------------------------------------
    def _update_birds(self, dt):
        """조류 행동 AI"""
        all_entities = list(self.world.entities)
        birds = [e for e in all_entities
                 if self._get_dna_flag(e, 'is_bird') and not self._get_dna_flag(e, 'is_egg')]

        # 사냥 가능 먹이(소형 동물) 목록 사전 수집
        prey_list = []
        for e in all_entities:
            dna = self._get(e, DNAComponent)
            if dna is None or dna.is_bird or dna.is_egg:
                continue
            if self._get(e, FoodComponent) is not None:
                continue
            h = self._get(e, HealthComponent)
            if h is None or h.current_health <= 0:
                continue
            if dna.size_gene <= BIRD_PREY_MAX_SIZE:
                p = self._get(e, PositionComponent)
                if p:
                    prey_list.append((e, p.x, p.y))

        mated_birds = set()

        for bird in birds:
            pos = self._get(bird, PositionComponent)
            dna = self._get(bird, DNAComponent)
            health = self._get(bird, HealthComponent)
            if pos is None or dna is None or health is None:
                continue
            if health.current_health <= 0:
                continue

            if health.mating_cooldown > 0:
                health.mating_cooldown -= dt

            life_pct = health.age / max(health.lifespan, 1.0)
            
            # 물 위에 있는 동안에는 배고픔 수치와 상관없이 항상 비행(사냥/탈출) 모드 유지
            current_biome = self.world_map.get_biome_at(pos.x, pos.y)
            is_in_water = current_biome in (2, 4)
            is_hunting = (health.energy < BIRD_ENERGY_HUNT) or is_in_water

            # 에너지 소모
            if is_hunting:
                drain = BIRD_WALK_DRAIN * BIRD_FLIGHT_DRAIN_MULT
            else:
                drain = BIRD_WALK_DRAIN * 0.3
            health.energy = max(0.0, health.energy - drain * dt)

            # 지형 디버프
            if not is_hunting:
                if current_biome == 1:  # 사막
                    health.energy = max(0.0, health.energy - 1.0 * dt)
                elif current_biome == 3:  # 설원
                    health.energy = max(0.0, health.energy - 1.5 * dt)

            # 에너지 소진 → 사망
            if health.energy <= 0:
                health.current_health = 0.0
                if self.logger:
                    self.logger.add_log(f"[아사] 새 ID:{bird} 에너지 소진 사망",
                                        color=(200, 100, 100), x=pos.x, y=pos.y, is_aquatic=False)
                    self.logger.logs[-1]["dead_stat"] = {
                        "id": bird,
                        "age": health.age,
                        "lifespan": health.lifespan,
                        "max_health": health.max_health,
                        "max_energy": health.max_energy,
                        "size": dna.size_gene,
                        "speed": dna.speed_gene,
                        "meta": dna.metabolism_gene,
                        "fur": 0.5,
                        "aquatic": 0.0,
                        "curiosity": 0.0,
                        "generation": getattr(dna, 'generation', 1),
                        "is_mutated": getattr(dna, 'is_mutated', False),
                        "is_bird": True,
                        "is_egg": False,
                        "is_amphibian": False,
                        "death_cause": "아사"
                    }
                continue

            # ============================================================
            # 1순위: 비행 사냥 모드 (에너지 < 80)
            # ============================================================
            if is_hunting and prey_list:
                nearest_prey = None
                min_prey_dist = float('inf')
                
                if _RUST_OK:
                    res = genesis_core.find_nearest_prey(pos.x, pos.y, prey_list)
                    if res is not None:
                        prey_id, px, py, min_prey_dist = res
                        nearest_prey = (prey_id, px, py)
                else:
                    for prey_id, px, py in prey_list:
                        d = math.hypot(pos.x - px, pos.y - py)
                        if d < min_prey_dist:
                            min_prey_dist = d
                            nearest_prey = (prey_id, px, py)

                if nearest_prey:
                    prey_id, px, py = nearest_prey

                    if min_prey_dist < BIRD_CATCH_RADIUS:
                        prey_health = self._get(prey_id, HealthComponent)
                        if prey_health:
                            prey_health.current_health = 0.0
                        if self.logger:
                            self.logger.add_log(f"[포식] 새 ID:{bird} 포식 성공!",
                                                color=(255, 80, 80), x=pos.x, y=pos.y, is_aquatic=False)
                        # 피식자 즉시 안전하게 삭제 (중복 KeyError 무시)
                        self._remove_entity(prey_id)
                        health.energy = BIRD_ENERGY_FULL
                        self._return_to_land(pos, dt)
                    else:
                        if min_prey_dist < BIRD_SLOW_RADIUS:
                            approach_speed = BIRD_APPROACH_SPEED
                        else:
                            approach_speed = BIRD_FLIGHT_SPEED
                        
                        prey_pos = self._get(prey_id, PositionComponent)
                        if prey_pos:
                            self._fly_toward(pos, prey_pos.x, prey_pos.y, approach_speed, dt)
                        else:
                            self._fly_toward(pos, px, py, approach_speed, dt)
                    continue

            # ============================================================
            # 2순위: 교배 (산책 중일 때만)
            # ============================================================
            desperate_mate = (life_pct >= 0.9 and health.mating_cooldown <= 0 and bird not in mated_birds)
            can_mate_walk = (not is_hunting and health.energy >= BIRD_MATE_MIN_ENERGY
                             and health.mating_cooldown <= 0 and bird not in mated_birds)
            can_mate = can_mate_walk or desperate_mate

            if can_mate:
                nearest_bird = None
                min_dist = float('inf')
                for other in birds:
                    if other == bird or other in mated_birds:
                        continue
                    o_h = self._get(other, HealthComponent)
                    if o_h is None or o_h.current_health <= 0:
                        continue
                    o_life_pct = o_h.age / max(o_h.lifespan, 1.0)
                    o_can = (o_h.energy >= BIRD_MATE_MIN_ENERGY and o_h.mating_cooldown <= 0) or \
                            (o_life_pct >= 0.9 and o_h.mating_cooldown <= 0)
                    if not o_can:
                        continue
                    o_pos = self._get(other, PositionComponent)
                    if o_pos is None:
                        continue
                    d = math.hypot(pos.x - o_pos.x, pos.y - o_pos.y)
                    if d < min_dist:
                        min_dist = d
                        nearest_bird = other

                if nearest_bird is not None:
                    m_pos = self._get(nearest_bird, PositionComponent)
                    if min_dist < 20.0:
                        # 교배 성공
                        m_health = self._get(nearest_bird, HealthComponent)
                        m_dna   = self._get(nearest_bird, DNAComponent)
                        health.energy   -= BIRD_MATE_COST
                        m_health.energy -= BIRD_MATE_COST
                        health.mating_cooldown   = 30.0
                        m_health.mating_cooldown = 30.0
                        health.mated_count   = getattr(health, 'mated_count', 0) + 1
                        m_health.mated_count = getattr(m_health, 'mated_count', 0) + 1
                        mated_birds.add(bird)
                        mated_birds.add(nearest_bird)

                        egg_count = random.randint(2, 3)
                        for _ in range(egg_count):
                            self._spawn_egg(pos, dna, m_dna)

                        if self.logger:
                            self.logger.add_log(
                                f"[산란] 새 ID:{bird} & {nearest_bird} 알 {egg_count}개 산란!",
                                color=(255, 200, 80), x=pos.x, y=pos.y, is_aquatic=False)

                        if desperate_mate or health.energy <= 0:
                            health.current_health = 0.0
                            if self.logger:
                                self.logger.add_log(f"[단회번식] 새 ID:{bird} 산란 후 탈진 사망",
                                                    color=(255, 105, 180), x=pos.x, y=pos.y, is_aquatic=False)
                                self.logger.logs[-1]["dead_stat"] = {
                                    "id": bird,
                                    "age": health.age,
                                    "lifespan": health.lifespan,
                                    "max_health": health.max_health,
                                    "max_energy": health.max_energy,
                                    "size": dna.size_gene,
                                    "speed": dna.speed_gene,
                                    "meta": dna.metabolism_gene,
                                    "fur": 0.5,
                                    "aquatic": 0.0,
                                    "curiosity": 0.0,
                                    "generation": getattr(dna, 'generation', 1),
                                    "is_mutated": getattr(dna, 'is_mutated', False),
                                    "is_bird": True,
                                    "is_egg": False,
                                    "is_amphibian": False,
                                    "death_cause": "단회번식 탈진사"
                                }
                        if m_health.energy <= 0:
                            m_health.current_health = 0.0
                            if self.logger:
                                self.logger.add_log(f"[단회번식] 새 ID:{nearest_bird} 산란 후 탈진 사망",
                                                    color=(255, 105, 180), x=m_pos.x, y=m_pos.y, is_aquatic=False)
                                self.logger.logs[-1]["dead_stat"] = {
                                    "id": nearest_bird,
                                    "age": m_health.age,
                                    "lifespan": m_health.lifespan,
                                    "max_health": m_health.max_health,
                                    "max_energy": m_health.max_energy,
                                    "size": m_dna.size_gene,
                                    "speed": m_dna.speed_gene,
                                    "meta": m_dna.metabolism_gene,
                                    "fur": 0.5,
                                    "aquatic": 0.0,
                                    "curiosity": 0.0,
                                    "generation": getattr(m_dna, 'generation', 1),
                                    "is_mutated": getattr(m_dna, 'is_mutated', False),
                                    "is_bird": True,
                                    "is_egg": False,
                                    "is_amphibian": False,
                                    "death_cause": "단회번식 탈진사"
                                }
                        continue
                    else:
                        if desperate_mate:
                            self._fly_toward(pos, m_pos.x, m_pos.y, BIRD_FLIGHT_SPEED, dt)
                        else:
                            self._walk_toward(pos, m_pos.x, m_pos.y, BIRD_WALK_SPEED, dt)
                        continue

            # ============================================================
            # 3순위: 산책 (육지 배회)
            # ============================================================
            if not is_hunting:
                if current_biome in (2, 4):
                    self._return_to_land(pos, dt)
                    continue
                self._wander(pos, BIRD_WALK_SPEED, dt)

            # 보더 밀어내기 마진
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

    # ---------------------------------------------------------------
    def _fly_toward(self, pos, tx, ty, speed, dt):
        dx = tx - pos.x
        dy = ty - pos.y
        length = math.hypot(dx, dy)
        if length < 1.0:
            return
        nx, ny = dx / length, dy / length
        
        target_angle = math.atan2(dy, dx)
        current_angle = getattr(pos, 'wander_angle', target_angle)
        angle_diff = (target_angle - current_angle + math.pi) % (2 * math.pi) - math.pi
        pos.wander_angle = current_angle + angle_diff * min(1.0, 10.0 * dt)
        
        move = min(speed * dt, length)
        pos.x += nx * move
        pos.y += ny * move
        pos.x = max(0, min(self.width, pos.x))
        pos.y = max(0, min(self.height, pos.y))

    def _walk_toward(self, pos, tx, ty, speed, dt):
        dx = tx - pos.x
        dy = ty - pos.y
        length = math.hypot(dx, dy)
        if length < 1.0:
            return
        nx, ny = dx / length, dy / length
        check_x = pos.x + nx * 40
        check_y = pos.y + ny * 40
        biome = self.world_map.get_biome_at(check_x, check_y)
        if biome in (2, 4):
            for i in range(16):
                angle = math.atan2(dy, dx) + (i - 8) * (math.pi / 8)
                sx, sy = math.cos(angle), math.sin(angle)
                tb = self.world_map.get_biome_at(pos.x + sx * 40, pos.y + sy * 40)
                if tb not in (2, 4):
                    nx, ny = sx, sy
                    break
                    
        target_angle = math.atan2(ny, nx)
        current_angle = getattr(pos, 'wander_angle', target_angle)
        angle_diff = (target_angle - current_angle + math.pi) % (2 * math.pi) - math.pi
        pos.wander_angle = current_angle + angle_diff * min(1.0, 8.0 * dt)
        
        move = min(speed * dt, length)
        pos.x += nx * move
        pos.y += ny * move

    def _wander(self, pos, speed, dt):
        pos.wander_timer = getattr(pos, 'wander_timer', 0.0) - dt
        if pos.wander_timer <= 0:
            chosen_angle = None
            for _ in range(12):
                angle = random.uniform(0, math.pi * 2)
                tx = pos.x + math.cos(angle) * 60
                ty = pos.y + math.sin(angle) * 60
                biome = self.world_map.get_biome_at(tx, ty)
                if biome not in (2, 4):
                    chosen_angle = angle
                    break
            if chosen_angle is None:
                chosen_angle = random.uniform(0, math.pi * 2)
            pos.wander_angle = chosen_angle
            pos.wander_timer = random.uniform(2.0, 5.0)
            
        pos.x += math.cos(pos.wander_angle) * speed * dt
        pos.y += math.sin(pos.wander_angle) * speed * dt

    def _return_to_land(self, pos, dt):
        """가장 가까운 육지 타일 방향으로 지속 탈출 (각도 고정 및 보간)"""
        current_biome = self.world_map.get_biome_at(pos.x, pos.y)
        if current_biome not in (2, 4):
            if hasattr(pos, 'return_angle'):
                delattr(pos, 'return_angle')
            return

        return_angle = getattr(pos, 'return_angle', None)
        if return_angle is None:
            best_angle = None
            for dist in [60, 120, 240, 500, 1000]:
                for i in range(16):
                    angle = i * (math.pi * 2 / 16)
                    tx = pos.x + math.cos(angle) * dist
                    ty = pos.y + math.sin(angle) * dist
                    b = self.world_map.get_biome_at(tx, ty)
                    if b not in (2, 4):
                        best_angle = angle
                        break
                if best_angle is not None:
                    break
            if best_angle is None:
                best_angle = random.uniform(0, math.pi * 2)
            pos.return_angle = best_angle
            return_angle = best_angle

        pos.wander_angle = return_angle
        move = BIRD_FLIGHT_SPEED * dt
        pos.x += math.cos(return_angle) * move
        pos.y += math.sin(return_angle) * move
        pos.x = max(0, min(self.width, pos.x))
        pos.y = max(0, min(self.height, pos.y))

    def _spawn_egg(self, pos, dna1, dna2):
        """교배 위치에 알 엔티티 스폰"""
        egg = self.world.create_entity()
        ex = pos.x + random.uniform(-15, 15)
        ey = pos.y + random.uniform(-15, 15)
        new_size = (dna1.size_gene + dna2.size_gene) / 2 * random.uniform(0.9, 1.1)
        new_speed = (dna1.speed_gene + dna2.speed_gene) / 2 * random.uniform(0.9, 1.1)
        new_meta = (dna1.metabolism_gene + dna2.metabolism_gene) / 2
        new_gen = max(dna1.generation, dna2.generation) + 1
        egg_dna = DNAComponent(
            size_gene=new_size,
            speed_gene=new_speed,
            color_gene=EGG_COLOR,
            metabolism_gene=new_meta,
            fur_gene=0.5,
            aquatic_gene=0.0,
            curiosity_gene=0.0,
            generation=new_gen,
            is_bird=True,
            is_egg=True,
            egg_timer=0.0,
        )
        self.world.add_component(egg, PositionComponent(ex, ey))
        self.world.add_component(egg, egg_dna)
        self.world.add_component(egg, RenderComponent(EGG_COLOR, EGG_SIZE))

    def _get(self, entity, comp_type):
        try:
            return self.world.get_component(entity, comp_type)
        except Exception:
            return None

    def _get_dna_flag(self, entity, flag):
        dna = self._get(entity, DNAComponent)
        return dna is not None and getattr(dna, flag, False)

    def _remove_entity(self, entity):
        # 중복 삭제 방지 (KeyError, ValueError 예외 차단)
        try:
            if entity in self.world.entities:
                self.world.entities.remove(entity)
        except ValueError:
            pass
        for comp_type in list(self.world.components.keys()):
            try:
                if entity in self.world.components[comp_type]:
                    del self.world.components[comp_type][entity]
            except KeyError:
                pass


def spawn_initial_birds(world, world_map, world_width, world_height, count=3):
    """월드 시작 시 조류 3마리 초기 스폰"""
    spawned = 0
    attempts = 0
    while spawned < count and attempts < 200:
        attempts += 1
        rx = random.uniform(100, world_width - 100)
        ry = random.uniform(100, world_height - 100)
        biome = world_map.get_biome_at(rx, ry)
        if biome not in (2, 4):  # 육지에만 스폰
            bird = world.create_entity()
            size_gene = random.uniform(0.8, 1.2)
            world.add_component(bird, PositionComponent(rx, ry))
            world.add_component(bird, DNAComponent(
                size_gene=size_gene,
                speed_gene=1.0,
                color_gene=BIRD_COLOR,
                metabolism_gene=1.0,
                fur_gene=0.5,
                aquatic_gene=0.0,
                curiosity_gene=0.0,
                generation=1,
                is_bird=True,
                is_egg=False,
            ))
            world.add_component(bird, RenderComponent(BIRD_COLOR, 10))
            world.add_component(bird, HealthComponent(
                current_health=100.0, max_health=100.0,
                age=0.0, lifespan=random.uniform(300, 600),
                energy=160.0, max_energy=160.0,
                mating_cooldown=0.0
            ))
            spawned += 1
    return spawned
