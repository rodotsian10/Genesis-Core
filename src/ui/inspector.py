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
        self.selected_dead_stat = None # 사망 개체 상세 정보 저장용
        pygame.font.init()
        try:
            self.font_title = pygame.font.SysFont('malgungothic', 24, bold=True)
            self.font_body = pygame.font.SysFont('malgungothic', 16)
        except:
            self.font_title = pygame.font.Font(None, 24)
            self.font_body = pygame.font.Font(None, 16)
        self.log_scroll = 0

    def handle_scroll(self, dy):
        self.log_scroll += int(dy) * 3
        if self.log_scroll < 0:
            self.log_scroll = 0

    def handle_click(self, mouse_x, mouse_y, camera, metabolism_system=None):
        if mouse_x >= self.screen_width - self.panel_width:
            if hasattr(self, 'visible_log_rects'):
                for rect, entry_dict in self.visible_log_rects:
                    if rect.collidepoint(mouse_x, mouse_y):
                        ent_id = entry_dict.get('entity_id')
                        if ent_id is not None and ent_id in self.world.entities:
                            if hasattr(camera, 'set_target'):
                                camera.set_target(ent_id, self.world)
                                self.selected_entity = ent_id
                                self.selected_dead_stat = None
                        else:
                            self.selected_entity = None
                            camera.clear_target()
                            if "dead_stat" in entry_dict:
                                self.selected_dead_stat = entry_dict["dead_stat"]
                            else:
                                self.selected_dead_stat = None
                                
                            x = entry_dict.get('x')
                            y = entry_dict.get('y')
                            if x is not None and y is not None:
                                camera.focus_on(x, y)
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
                    self.selected_dead_stat = None
                    camera.set_target(entity, self.world)
                    clicked = True
                    break
                    
            if not clicked:
                self.selected_entity = None
                self.selected_dead_stat = None
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
                # 종족 판별
                species = "육지 생물"
                if dna:
                    if getattr(dna, 'is_egg', False):
                        species = "알"
                    elif getattr(dna, 'is_bird', False):
                        species = "조류"
                    elif getattr(dna, 'is_amphibian', False):
                        species = "양서류"
                    elif getattr(dna, 'aquatic_gene', 0.0) >= 0.5:
                        species = "바다 생물"
                
                text_surf = self.font_body.render(f"나이: {health.age:.1f} / {health.lifespan:.1f} ({species})", True, (150, 150, 150))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 30
                
                text_surf = self.font_body.render(f"체력: {int(health.current_health)}/{int(health.max_health)}", True, (200, 80, 80))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                pygame.draw.rect(screen, (100, 100, 100), pygame.Rect(margin, y_offset, self.panel_width-30, 10))
                pygame.draw.rect(screen, (200, 80, 80), pygame.Rect(margin, y_offset, int((self.panel_width-30)*min(1.0, max(0, health.current_health)/health.max_health)), 10))
                y_offset += 25
                
                text_surf = self.font_body.render(f"에너지: {int(health.energy)}/{int(health.max_energy)}", True, (50, 200, 100))
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                pygame.draw.rect(screen, (100, 100, 100), pygame.Rect(margin, y_offset, self.panel_width-30, 10))
                pygame.draw.rect(screen, (50, 200, 100), pygame.Rect(margin, y_offset, int((self.panel_width-30)*min(1.0, max(0, health.energy)/health.max_energy)), 10))
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
                # 돌연변이 상태 & 세대 정보 출력
                gen_val = getattr(dna, 'generation', 1)
                is_mut = getattr(dna, 'is_mutated', False)
                mut_feats = getattr(dna, 'mutated_features', {})
                if not isinstance(mut_feats, dict):
                    mut_feats = {}
                mut_str = "돌연변이 계열 (위험)" if is_mut else "일반 계열"
                mut_color = (255, 100, 100) if is_mut else (100, 200, 255)
                
                text_surf = self.font_body.render(f"유전: {mut_str} ({gen_val}세대)", True, mut_color)
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 25
                
                # 각 유전자별 돌연변이 여부에 따라 빨간색 텍스트와 변화 수치 적용
                size_color = (255, 80, 80) if "크기" in mut_feats else (150, 150, 150)
                size_suffix = f" ({mut_feats['크기']})" if "크기" in mut_feats else ""
                text_surf = self.font_body.render(f"크기 (Size): {dna.size_gene:.2f}{size_suffix}", True, size_color)
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                
                speed_color = (255, 80, 80) if "속도" in mut_feats else (150, 150, 150)
                speed_suffix = f" ({mut_feats['속도']})" if "속도" in mut_feats else ""
                text_surf = self.font_body.render(f"속도 (Speed): {dna.speed_gene:.2f}{speed_suffix}", True, speed_color)
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                
                meta_color = (255, 80, 80) if "대사량" in mut_feats else (150, 150, 150)
                meta_suffix = f" ({mut_feats['대사량']})" if "대사량" in mut_feats else ""
                text_surf = self.font_body.render(f"대사량 (Meta): {dna.metabolism_gene:.2f}{meta_suffix}", True, meta_color)
                screen.blit(text_surf, (margin, y_offset))
                y_offset += 20
                
                if hasattr(dna, 'fur_gene'):
                    fur_color = (255, 100, 100) if "털" in mut_feats else (200, 200, 200)
                    fur_suffix = f" ({mut_feats['털']})" if "털" in mut_feats else ""
                    text_surf = self.font_body.render(f"털 밀도 (Fur): {dna.fur_gene:.2f}{fur_suffix}", True, fur_color)
                    screen.blit(text_surf, (margin, y_offset))
                    y_offset += 20
                if hasattr(dna, 'aquatic_gene'):
                    aquatic_pct = int(dna.aquatic_gene * 100)
                    aq_color = (255, 100, 100) if "친수성" in mut_feats else ((80, 120, 255) if dna.aquatic_gene >= 0.5 else (180, 140, 80))
                    aq_suffix = f" ({mut_feats['친수성']})" if "친수성" in mut_feats else ""
                    text_surf = self.font_body.render(f"친수성: {aquatic_pct}%{aq_suffix}", True, aq_color)
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
                    cur_color = (255, 100, 100) if "호기심" in mut_feats else ((255, 200, 50) if eff_cur > 0.3 else (120, 120, 120))
                    cur_suffix = f" ({mut_feats['호기심']})" if "호기심" in mut_feats else ""
                    text_surf = self.font_body.render(f"호기심: {int(dna.curiosity_gene*100)}% (실:{int(eff_cur*100)}%){cur_suffix}", True, cur_color)
                    screen.blit(text_surf, (margin, y_offset))
                    y_offset += 20
                y_offset += 10
                
            if pos:
                text_surf = self.font_body.render(f"좌표: ({int(pos.x)}, {int(pos.y)})", True, (100, 100, 100))
                screen.blit(text_surf, (margin, y_offset))

        elif self.selected_dead_stat is not None:
            # 사망 개체 기록 디스플레이
            ds = self.selected_dead_stat
            text_surf = self.font_title.render(f"사망 정보 (ID: {ds['id']})", True, (255, 100, 100))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 40

            text_surf = self.font_body.render(f"사인: {ds['death_cause']}", True, (255, 80, 80))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 25

            # 종족 판별
            species = "육지 생물"
            if ds.get('is_egg', False):
                species = "알"
            elif ds.get('is_bird', False):
                species = "조류"
            elif ds.get('is_amphibian', False):
                species = "양서류"
            elif ds.get('aquatic', 0.0) >= 0.5:
                species = "바다 생물"

            text_surf = self.font_body.render(f"최종 나이: {ds['age']:.1f} / {ds['lifespan']:.1f} ({species})", True, (150, 150, 150))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 25

            ds_mut_feats = ds.get('mutated_features', {})
            if not isinstance(ds_mut_feats, dict):
                ds_mut_feats = {}
            mut_str = "돌연변이 계열 (위험)" if ds['is_mutated'] else "일반 계열"
            mut_color = (255, 100, 100) if ds['is_mutated'] else (100, 200, 255)
            text_surf = self.font_body.render(f"유전: {mut_str} ({ds['generation']}세대)", True, mut_color)
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 30

            size_color = (255, 80, 80) if "크기" in ds_mut_feats else (150, 150, 150)
            size_suffix = f" ({ds_mut_feats['크기']})" if "크기" in ds_mut_feats else ""
            text_surf = self.font_body.render(f"크기 (Size): {ds['size']:.2f}{size_suffix}", True, size_color)
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            
            speed_color = (255, 80, 80) if "속도" in ds_mut_feats else (150, 150, 150)
            speed_suffix = f" ({ds_mut_feats['속도']})" if "속도" in ds_mut_feats else ""
            text_surf = self.font_body.render(f"속도 (Speed): {ds['speed']:.2f}{speed_suffix}", True, speed_color)
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            
            meta_color = (255, 80, 80) if "대사량" in ds_mut_feats else (150, 150, 150)
            meta_suffix = f" ({ds_mut_feats['대사량']})" if "대사량" in ds_mut_feats else ""
            text_surf = self.font_body.render(f"대사량 (Meta): {ds['meta']:.2f}{meta_suffix}", True, meta_color)
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            
            fur_color = (255, 100, 100) if "털" in ds_mut_feats else (200, 200, 200)
            fur_suffix = f" ({ds_mut_feats['털']})" if "털" in ds_mut_feats else ""
            text_surf = self.font_body.render(f"털 밀도 (Fur): {ds['fur']:.2f}{fur_suffix}", True, fur_color)
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            
            aquatic_pct = int(ds['aquatic'] * 100)
            aq_color = (255, 100, 100) if "친수성" in ds_mut_feats else ((80, 120, 255) if ds['aquatic'] >= 0.5 else (180, 140, 80))
            aq_suffix = f" ({ds_mut_feats['친수성']})" if "친수성" in ds_mut_feats else ""
            text_surf = self.font_body.render(f"친수성: {aquatic_pct}%{aq_suffix}", True, aq_color)
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            
            cur_color = (255, 100, 100) if "호기심" in ds_mut_feats else (255, 200, 50)
            cur_suffix = f" ({ds_mut_feats['호기심']})" if "호기심" in ds_mut_feats else ""
            text_surf = self.font_body.render(f"호기심: {int(ds['curiosity']*100)}%{cur_suffix}", True, cur_color)
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
                
        else:
            text_surf = self.font_title.render("관찰자 모드", True, (200, 200, 200))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 40
            text_surf = self.font_body.render("개체 또는 로그 클릭하여 상세 확인", True, (150, 150, 150))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            text_surf = self.font_body.render("마우스 휠: 확대/축소", True, (150, 150, 150))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            text_surf = self.font_body.render("우클릭 & 드래그: 맵 이동", True, (150, 150, 150))
            screen.blit(text_surf, (margin, y_offset))
            y_offset += 20
            
        if self.selected_entity is not None and self.selected_entity in self.world.entities:
            # 로그 뷰 영역 렌더링
            pass
        
        # 로그 렌더링 패널 하단 영역 그리기
        self.visible_log_rects = []
        if self.logger:
            log_start_y = self.screen_height - 240
            pygame.draw.line(screen, (80, 80, 80), (self.screen_width - self.panel_width, log_start_y - 10), (self.screen_width, log_start_y - 10), 1)
            
            title_log = self.font_body.render("실시간 로그 기록", True, (220, 220, 120))
            screen.blit(title_log, (margin, log_start_y))
            log_start_y += 22
            
            visible_count = 10
            logs_to_show = self.logger.logs[-visible_count - self.log_scroll:]
            if len(self.logger.logs) > visible_count + self.log_scroll:
                logs_to_show = logs_to_show[:visible_count]
                
            max_text_width = self.panel_width - 30

            # 텍스트 자동 줄바꿈 헬퍼 함수
            def wrap_text(text, font_obj, max_w):
                words = text.split(' ')
                lines = []
                current_line = []
                for word in words:
                    # 단어 단위로 쪼개기
                    test_line = ' '.join(current_line + [word])
                    test_w, _ = font_obj.size(test_line)
                    if test_w <= max_w:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                            current_line = [word]
                        else:
                            # 단어 자체가 가로폭보다 긴 비정상적인 경우 강제 분리
                            lines.append(word)
                            current_line = []
                if current_line:
                    lines.append(' '.join(current_line))
                return lines

            for entry in logs_to_show:
                msg = entry.get("msg", "")
                col = entry.get("color") or (200, 200, 200)
                
                # 래핑된 줄 목록 가져오기
                wrapped_lines = wrap_text(msg, self.font_body, max_text_width)
                
                # 래핑된 여러 줄들을 연속해서 그립니다.
                log_entry_rect = None
                for line_idx, line in enumerate(wrapped_lines):
                    txt = self.font_body.render(line, True, col)
                    r_rect = txt.get_rect(topleft=(margin, log_start_y))
                    
                    # 마우스 클릭 판정은 첫 줄 또는 전체 영역 커버용으로 셋업
                    if log_entry_rect is None:
                        log_entry_rect = pygame.Rect(margin, log_start_y, max_text_width, 18 * len(wrapped_lines))
                    
                    screen.blit(txt, (margin, log_start_y))
                    log_start_y += 18
                
                if log_entry_rect is not None:
                    self.visible_log_rects.append((log_entry_rect, entry))
                # 항목 간 여백 추가
                log_start_y += 2
