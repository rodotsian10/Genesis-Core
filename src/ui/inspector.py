import pygame
import math
from ecs.components import PositionComponent, RenderComponent, HealthComponent, DNAComponent

class InspectorUI:
    def __init__(self, world, screen_width, screen_height, panel_width=250):
        self.world = world
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.panel_width = panel_width
        self.selected_entity = None
        pygame.font.init()
        try:
            self.font_title = pygame.font.SysFont('malgungothic', 24, bold=True)
            self.font_body = pygame.font.SysFont('malgungothic', 16)
        except:
            self.font_title = pygame.font.Font(None, 24)
            self.font_body = pygame.font.Font(None, 16)
        self.log_scroll = 0

    def handle_scroll(self, dy):
        # dy는 마우스 휠 위로 굴릴 때 1, 아래로 굴릴 때 -1
        # 스크롤을 올리면(양수) 과거 로그(위쪽)를 본다 -> log_scroll 증가
        self.log_scroll += int(dy) * 3
        if self.log_scroll < 0:
            self.log_scroll = 0

    def handle_click(self, mouse_x, mouse_y, camera, metabolism_system=None):
        if mouse_x >= self.screen_width - self.panel_width:
            if hasattr(self, 'visible_log_rects'):
                for rect, entry_dict in self.visible_log_rects:
                    if rect.collidepoint(mouse_x, mouse_y):
                        ent_id = entry_dict.get('entity_id')
                        # 1) 개체가 아직 살아있으면 카메라 추적 대상으로 지정
                        if ent_id is not None and ent_id in self.world.entities:
                            if hasattr(camera, 'set_target'):
                                camera.set_target(ent_id, self.world)
                                self.selected_entity = ent_id
                        else:
                            # 2) 개체가 죽었거나 좌표 정보가 있는 경우 카메라 화면 중심 이동 및 데스마커 부활
                            self.selected_entity = None
                            camera.clear_target()
                            x = entry_dict.get('x')
                            y = entry_dict.get('y')
                            if x is not None and y is not None:
                                camera.focus_on(x, y)
                                # 데스마커 부활/생성 (metabolism_system)
                                if metabolism_system is not None:
                                    found = False
                                    for marker in metabolism_system.death_markers:
                                        if abs(marker['x'] - x) < 1.0 and abs(marker['y'] - y) < 1.0:
                                            marker['timer'] = 5.0
                                            found = True
                                            break
                                    if not found:
                                        metabolism_system.death_markers.append({
                                            'x': x,
                                            'y': y,
                                            'timer': 5.0,
                                            'is_aquatic': entry_dict.get('is_aquatic', False)
                                        })
                        return True
            return False

        if mouse_x < self.screen_width - self.panel_width:
            world_x, world_y = camera.screen_to_world(mouse_x, mouse_y)
            entities = self.world.get_entities_with(PositionComponent, RenderComponent)
            
            clicked = False
            for entity in entities:
                pos = self.world.get_component(entity, PositionComponent)
                render = self.world.get_component(entity, RenderComponent)
                
                if math.hypot(pos.x - world_x, pos.y - world_y) < render.size:
                    self.selected_entity = entity
                    camera.set_target(entity, self.world)
                    clicked = True
                    break
                    
            if not clicked:
                self.selected_entity = None
                camera.clear_target()
        return False

    def render(self, screen):
        panel_rect = pygame.Rect(self.screen_width - self.panel_width, 0, self.panel_width, self.screen_height)
        pygame.draw.rect(screen, (30, 30, 30), panel_rect)
        pygame.draw.line(screen, (100, 100, 100), (self.screen_width - self.panel_width, 0), (self.screen_width - self.panel_width, self.screen_height), 2)
        
        margin = self.screen_width - self.panel_width + 15
        y_offset = 20
        
        if self.selected_entity is not None and self.selected_entity in self.world.entities:
            text_surf = self.font_title.render(f"개체 정보 (ID: {self.selected_entity})", True, (200, 200, 200))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 40
            
            health = self.world.get_component(self.selected_entity, HealthComponent)
            dna = self.world.get_component(self.selected_entity, DNAComponent)
            pos = self.world.get_component(self.selected_entity, PositionComponent)
            
            if health:
                text_surf = self.font_body.render(f"나이: {health.age:.1f} / {health.lifespan:.1f}", True, (150, 150, 150))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 30
                
                text_surf = self.font_body.render(f"체력: {int(health.current_health)}/{int(health.max_health)}", True, (200, 80, 80))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                pygame.draw.rect(screen, (100, 100, 100), pygame.Rect(margin, y_offset, self.panel_width-30, 10))
                pygame.draw.rect(screen, (200, 80, 80), pygame.Rect(margin, y_offset, (self.panel_width-30)*min(1.0, max(0, health.current_health)/health.max_health), 10))
                y_offset += 25
                
                text_surf = self.font_body.render(f"에너지: {int(health.energy)}/{int(health.max_energy)}", True, (50, 200, 100))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                pygame.draw.rect(screen, (100, 100, 100), pygame.Rect(margin, y_offset, self.panel_width-30, 10))
                pygame.draw.rect(screen, (50, 200, 100), pygame.Rect(margin, y_offset, (self.panel_width-30)*min(1.0, max(0, health.energy)/health.max_energy), 10))
                y_offset += 25
                
                # 호흡 게이지
                breath_val = getattr(health, 'breath', health.max_health)
                max_breath_val = getattr(health, 'max_breath', health.max_health)
                breath_pct = min(1.0, max(0, breath_val / max_breath_val))
                breath_color = (100, 150, 255) if breath_pct > 0.4 else (255, 80, 80)
                text_surf = self.font_body.render(f"호흡: {int(breath_val)}/{int(max_breath_val)}", True, breath_color)
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                pygame.draw.rect(screen, (100, 100, 100), pygame.Rect(margin, y_offset, self.panel_width-30, 10))
                pygame.draw.rect(screen, breath_color, pygame.Rect(margin, y_offset, int((self.panel_width-30)*breath_pct), 10))
                y_offset += 30
                
            if dna:
                text_surf = self.font_body.render(f"크기 (Size): {dna.size_gene:.2f}", True, (150, 150, 150))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                text_surf = self.font_body.render(f"속도 (Speed): {dna.speed_gene:.2f}", True, (150, 150, 150))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                text_surf = self.font_body.render(f"대사량 (Meta): {dna.metabolism_gene:.2f}", True, (150, 150, 150))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                if hasattr(dna, 'fur_gene'):
                    text_surf = self.font_body.render(f"털 밀도 (Fur): {dna.fur_gene:.2f}", True, (200, 200, 200))
                    screen.blit(text_surf, (margin, y_offset))
                    y_offset += 20
                if hasattr(dna, 'aquatic_gene'):
                    aquatic_pct = int(dna.aquatic_gene * 100)
                    aquatic_color = (80, 120, 255) if dna.aquatic_gene >= 0.5 else (180, 140, 80)
                    text_surf = self.font_body.render(f"친수성: {aquatic_pct}%", True, aquatic_color)
                    screen.blit(text_surf, (margin, y_offset))
                    y_offset += 20
                if hasattr(dna, 'curiosity_gene') and health:
                    life_pct = health.age / max(health.lifespan, 1.0)
                    if life_pct < 0.6:
                        eff_cur = dna.curiosity_gene
                    elif life_pct < 0.8:
                        eff_cur = dna.curiosity_gene * (1.0 - (life_pct - 0.6) / 0.2)
                    else:
                        eff_cur = 0.0
                    cur_color = (255, 200, 50) if eff_cur > 0.3 else (120, 120, 120)
                    text_surf = self.font_body.render(f"호기심: {int(dna.curiosity_gene*100)}% (실:{int(eff_cur*100)}%)", True, cur_color)
                    screen.blit(text_surf, (margin, y_offset))
                    y_offset += 20
                y_offset += 10
                
            if pos:
                text_surf = self.font_body.render(f"좌표: ({int(pos.x)}, {int(pos.y)})", True, (100, 100, 100))
                screen.blit(text_surf, (margin, y_offset))
                
        else:
            text_surf = self.font_title.render("관찰자 모드", True, (200, 200, 200))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 40
            text_surf = self.font_body.render("개체를 클릭하여 상세 확인", True, (150, 150, 150))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            text_surf = self.font_body.render("마우스 휠: 확대/축소", True, (150, 150, 150))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            text_surf = self.font_body.render("우클릭 & 드래그: 맵 이동", True, (150, 150, 150))
            screen.blit(text_surf, (margin, y_offset))

        # 하단 로그 패널 (줄바꿈 및 스크롤 지원)
        log_y_start = self.screen_height // 2 + 20
        pygame.draw.line(screen, (139, 69, 19), (self.screen_width - self.panel_width, log_y_start), (self.screen_width, log_y_start), 3)
        text_surf = self.font_title.render("월드 이벤트 로그", True, (200, 200, 200))
        screen.blit(text_surf, (margin, log_y_start + 10))
        
        if hasattr(self, 'logger') and self.logger:
            log_area_height = self.screen_height - log_y_start - 40
            lines_can_fit = log_area_height // 20
            
            wrapped_logs = []
            for log_entry in self.logger.logs:
                # Handle both new dict format and old string format
                if isinstance(log_entry, dict):
                    msg = f"[{log_entry.get('time', '')}] {log_entry.get('msg', '')}"
                    ent_id = log_entry.get('entity_id')
                    custom_color = log_entry.get('color')
                    entry_dict = log_entry
                else:
                    msg = log_entry
                    ent_id = None
                    custom_color = None
                    entry_dict = {"msg": log_entry}
                    
                words = msg.split(' ')
                current_line = ""
                for word in words:
                    test_line = current_line + word + " "
                    if self.font_body.size(test_line)[0] > self.panel_width - 30:
                        if current_line:
                            wrapped_logs.append((current_line, ent_id, custom_color, entry_dict))
                        current_line = word + " "
                    else:
                        current_line = test_line
                if current_line:
                    wrapped_logs.append((current_line, ent_id, custom_color, entry_dict))
                    
            max_scroll = max(0, len(wrapped_logs) - lines_can_fit)
            if self.log_scroll > max_scroll:
                self.log_scroll = max_scroll
                
            start_idx = max(0, len(wrapped_logs) - lines_can_fit - self.log_scroll)
            end_idx = start_idx + lines_can_fit
            
            visible_logs = wrapped_logs[start_idx:end_idx]
            
            self.visible_log_rects = []
            log_y = log_y_start + 40
            for log_msg, ent_id, custom_color, entry_dict in visible_logs:
                if custom_color:
                    color = custom_color
                elif ent_id is not None:
                    color = (255, 255, 100)
                else:
                    color = (200, 200, 200)
                log_surf = self.font_body.render(log_msg, True, color)
                rect = screen.blit(log_surf, (margin, log_y))
                self.visible_log_rects.append((rect, entry_dict))
                log_y += 20
