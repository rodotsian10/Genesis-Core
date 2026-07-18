import pygame
import sys
import random
from ecs.core import World
from ecs.components import PositionComponent, RenderComponent, HealthComponent, DNAComponent, FoodComponent
from ecs.systems import MetabolismSystem, RenderSystem, SurvivalSystem
from ecs.systems_environment import PlantSpawnSystem
from ecs.systems_birds import BirdSystem, spawn_initial_birds
from ui.inspector import InspectorUI
from ui.restart_ui import RestartUI
from camera import Camera
from logger import EventLogger
from world_map import WorldMap


def build_world(options=None):
    """월드 및 시스템 초기화. options 딕셔너리로 모드 제어."""
    if options is None:
        options = {}
    enable_birds = options.get('enable_birds', True)
    enable_amphibians = options.get('enable_amphibians', True)

    width, height = 1200, 720
    world_width, world_height = 4000, 4000
    ui_panel_width = 300

    world = World()
    world_map = WorldMap(world_width, world_height)
    
    # 러스트 바인딩 모듈에 월드 지형 정보 캐싱 전송 (1차원 플랫 리스트로 변환)
    flat_grid = []
    for x in range(world_map.cols):
        flat_grid.extend(world_map.grid[x])
    try:
        import genesis_core
        genesis_core.set_world_map(world_map.cols, world_map.rows, float(world_map.tile_size), flat_grid)
    except Exception as e:
        print("Rust set_world_map failed:", e)

    logger = EventLogger(max_logs=100)

    survival_system = SurvivalSystem(world, world_map, world_width, world_height,
                                     max_population=500, logger=logger,
                                     enable_amphibians=enable_amphibians)
    metabolism_system = MetabolismSystem(world, world_map, logger=logger)
    plant_system = PlantSpawnSystem(world, world_map, world_width, world_height, max_plants=2000)
    bird_system = BirdSystem(world, world_map, world_width, world_height, logger=logger) if enable_birds else None

    # 초기 생명체 스폰 (육지/바다 100마리)
    spawn_count = 0
    while spawn_count < 100:
        size_gene = random.uniform(0.5, 2.0)
        speed_gene = random.uniform(0.5, 2.0)
        metabolism_gene = random.uniform(0.8, 1.2)
        colors = [(138, 182, 102), (217, 160, 102), (200, 100, 100), (100, 150, 200), (220, 200, 100)]
        color_gene = random.choice(colors)
        fur_gene = random.uniform(0.0, 1.0)
        aquatic_gene = random.uniform(0.0, 1.0)
        curiosity_gene = random.uniform(0.0, 1.0)

        is_aquatic = aquatic_gene >= 0.5
        found_pos = False
        attempts = 0
        rx, ry = 0.0, 0.0
        while not found_pos and attempts < 100:
            rx = random.uniform(0, world_width)
            ry = random.uniform(0, world_height)
            biome = world_map.get_biome_at(rx, ry)
            if is_aquatic and biome in (2, 4):
                found_pos = True
            elif not is_aquatic and biome == 0:
                found_pos = True
            attempts += 1

        if found_pos:
            entity = world.create_entity()
            world.add_component(entity, PositionComponent(rx, ry))
            world.add_component(entity, DNAComponent(
                size_gene=size_gene,
                speed_gene=speed_gene,
                color_gene=color_gene,
                metabolism_gene=metabolism_gene,
                fur_gene=fur_gene,
                aquatic_gene=aquatic_gene,
                curiosity_gene=curiosity_gene,
                generation=1
            ))
            actual_size = int(16 * size_gene)
            world.add_component(entity, RenderComponent(color_gene, actual_size))
            world.add_component(entity, HealthComponent(
                current_health=100.0, max_health=100.0,
                age=random.uniform(0, 50), lifespan=random.uniform(100, 250),
                energy=100.0, max_energy=100.0
            ))
            spawn_count += 1

    # 조류 초기 스폰 (활성화 시 3마리)
    if enable_birds:
        spawn_initial_birds(world, world_map, world_width, world_height, count=3)

    return world, world_map, logger, survival_system, metabolism_system, plant_system, bird_system


def main():
    pygame.init()
    width, height = 1200, 720
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Genesis Core")
    clock = pygame.time.Clock()

    world_width, world_height = 4000, 4000
    ui_panel_width = 300

    camera = Camera(width, height, world_width, world_height)
    restart_ui = RestartUI(width, height)

    current_options = {'enable_birds': True, 'enable_amphibians': True}

    (world, world_map, logger,
     survival_system, metabolism_system,
     plant_system, bird_system) = build_world(current_options)

    render_system = RenderSystem(world, screen, camera, world_width, world_height)
    ui = InspectorUI(world, width, height, ui_panel_width)
    ui.logger = logger

    # 재시작 버튼 영역 (왼쪽 하단)
    restart_btn_rect = pygame.Rect(10, height - 36, 100, 26)

    # 종족별 클릭 영역 매핑을 위한 딕셔너리
    hud_click_rects = {}

    running = True
    is_panning = False

    while running:
        dt = clock.tick(60) / 1000.0

        # 재시작 요청 처리
        if restart_ui.restart_requested:
            restart_ui.restart_requested = False
            current_options = restart_ui.restart_options
            camera = Camera(width, height, world_width, world_height)
            (world, world_map, logger,
             survival_system, metabolism_system,
             plant_system, bird_system) = build_world(current_options)
            render_system = RenderSystem(world, screen, camera, world_width, world_height)
            ui = InspectorUI(world, width, height, ui_panel_width)
            ui.logger = logger
            continue

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # restart_ui가 열려있으면 이벤트 우선 전달
            if restart_ui.handle_event(event):
                continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx, my = event.pos
                    # 1) 재시작 설정 버튼 클릭 확인
                    if restart_btn_rect.collidepoint(mx, my):
                        restart_ui.toggle()
                        continue

                    # 2) HUD 종족 레이블 클릭 감지 및 랜덤 개체 선택 기능
                    hud_clicked = False
                    for species_type, rect in hud_click_rects.items():
                        if rect.collidepoint(mx, my):
                            all_entities = world.get_entities_with(DNAComponent)
                            candidates = []
                            for ent in all_entities:
                                dna = world.get_component(ent, DNAComponent)
                                if species_type == "육지":
                                    if not getattr(dna, 'is_bird', False) and not getattr(dna, 'is_egg', False) and not getattr(dna, 'is_amphibian', False) and getattr(dna, 'aquatic_gene', 0.0) < 0.5:
                                        candidates.append(ent)
                                elif species_type == "바다":
                                    if not getattr(dna, 'is_bird', False) and not getattr(dna, 'is_egg', False) and not getattr(dna, 'is_amphibian', False) and getattr(dna, 'aquatic_gene', 0.0) >= 0.5:
                                        candidates.append(ent)
                                elif species_type == "양서":
                                    if getattr(dna, 'is_amphibian', False):
                                        candidates.append(ent)
                                elif species_type == "새":
                                    if getattr(dna, 'is_bird', False) and not getattr(dna, 'is_egg', False):
                                        candidates.append(ent)
                                elif species_type == "알":
                                    if getattr(dna, 'is_egg', False):
                                        candidates.append(ent)

                            if candidates:
                                selected = random.choice(candidates)
                                ui.selected_entity = selected
                                ui.selected_dead_stat = None
                                camera.set_target(selected, world)
                                logger.add_log(f"[추적] {species_type} 종족 임의 개체 ID:{selected}를 선택하여 카메라 추적을 시작합니다.", color=(200, 220, 255))
                            hud_clicked = True
                            break
                    
                    if hud_clicked:
                        continue

                    # 3) 일반 월드 인스펙터 클릭
                    ui.handle_click(mx, my, camera, metabolism_system)

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
        if bird_system:
            bird_system.update(dt)

        # 렌더링
        screen.fill((0, 0, 0))
        world_map.render(screen, camera)
        render_system.update()

        # 사망 마커
        for marker in metabolism_system.death_markers:
            sx, sy = camera.apply(marker['x'], marker['y'])
            if 0 <= sx < width - ui_panel_width and 0 <= sy < height:
                alpha = int(max(0, min(255, (marker['timer'] / 5.0) * 255)))
                color = (120, 160, 255) if marker['is_aquatic'] else (255, 110, 110)
                size = int(6 * camera.zoom)
                if size < 2: size = 2
                s = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.line(s, (*color, alpha), (size, 0), (size, size * 2), 2)
                pygame.draw.line(s, (*color, alpha), (0, size), (size * 2, size), 2)
                screen.blit(s, (sx - size, sy - size))

        ui.render(screen)

        # 재시작 버튼 (왼쪽 하단)
        btn_color = (40, 60, 110)
        mx, my = pygame.mouse.get_pos()
        if restart_btn_rect.collidepoint(mx, my):
            btn_color = (60, 90, 160)
        pygame.draw.rect(screen, btn_color, restart_btn_rect, border_radius=5)
        pygame.draw.rect(screen, (100, 140, 200), restart_btn_rect, 1, border_radius=5)
        font_btn = pygame.font.SysFont('malgungothic', 13, bold=True)
        btn_txt = font_btn.render("재시작 설정", True, (200, 220, 255))
        screen.blit(btn_txt, (restart_btn_rect.x + 8, restart_btn_rect.y + 6))

        # 재시작 UI 팝업
        restart_ui.render(screen)

        # 인구 통계 및 클릭 좌표 맵 갱신
        font = pygame.font.SysFont('malgungothic', 16)
        all_dna_entities = world.get_entities_with(DNAComponent)
        land_count = sea_count = bird_count = egg_count = amphi_count = 0
        for e in all_dna_entities:
            dna = world.get_component(e, DNAComponent)
            if getattr(dna, 'is_egg', False):
                egg_count += 1
            elif getattr(dna, 'is_bird', False):
                bird_count += 1
            elif getattr(dna, 'is_amphibian', False):
                amphi_count += 1
            elif getattr(dna, 'aquatic_gene', 0.0) >= 0.5:
                sea_count += 1
            else:
                land_count += 1

        pop_count = len(all_dna_entities)
        food_count = len(world.get_entities_with(FoodComponent))

        # HUD 텍스트 분절 렌더링 및 개별 클릭용 영역 설정
        hud_click_rects.clear()
        current_x = 10
        y_pos = 10

        def draw_text_with_outline(text_str, text_color, x, y):
            # 상하좌우 1px 검은색 테두리 그림자 겹쳐 그리기
            outline_surf = font.render(text_str, True, (0, 0, 0))
            for dx in (-1, 1):
                for dy in (-1, 1):
                    screen.blit(outline_surf, (x + dx, y + dy))
            # 전경색 그리기
            foreground_surf = font.render(text_str, True, text_color)
            screen.blit(foreground_surf, (x, y))
            return foreground_surf.get_width(), foreground_surf.get_height()

        # 1) 기본 인구 텍스트
        w, h = draw_text_with_outline(f"인구: {pop_count}/500  ", (255, 255, 255), current_x, y_pos)
        current_x += w

        # 2) 육지
        w, h = draw_text_with_outline(f"육지:{land_count}  ", (138, 182, 102), current_x, y_pos)
        hud_click_rects["육지"] = pygame.Rect(current_x, y_pos, w, h)
        current_x += w

        # 3) 바다
        w, h = draw_text_with_outline(f"바다:{sea_count}  ", (100, 150, 200), current_x, y_pos)
        hud_click_rects["바다"] = pygame.Rect(current_x, y_pos, w, h)
        current_x += w

        # 4) 양서
        w, h = draw_text_with_outline(f"양서:{amphi_count}  ", (60, 180, 160), current_x, y_pos)
        hud_click_rects["양서"] = pygame.Rect(current_x, y_pos, w, h)
        current_x += w

        # 5) 새
        w, h = draw_text_with_outline(f"새:{bird_count}  ", (220, 180, 80), current_x, y_pos)
        hud_click_rects["새"] = pygame.Rect(current_x, y_pos, w, h)
        current_x += w

        # 6) 알
        w, h = draw_text_with_outline(f"알:{egg_count}  ", (240, 220, 180), current_x, y_pos)
        hud_click_rects["알"] = pygame.Rect(current_x, y_pos, w, h)
        current_x += w

        # 7) 식량 마무리
        draw_text_with_outline(f"|  식량: {food_count}/2000", (200, 200, 200), current_x, y_pos)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
