import pygame

class RestartUI:
    """재시작 옵션 팝업 창 - 양서류/조류 모드 온오프 및 월드 재시작"""
    
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.visible = False
        
        # 옵션 상태
        self.enable_birds = True
        self.enable_amphibians = True
        
        # 재시작 트리거
        self.restart_requested = False
        self.restart_options = {}
        
        # 폰트
        self.font_title = pygame.font.SysFont("malgungothic", 20, bold=True)
        self.font_body  = pygame.font.SysFont("malgungothic", 15)
        self.font_btn   = pygame.font.SysFont("malgungothic", 14, bold=True)
        
        # 팝업 크기/위치
        self.popup_w = 380
        self.popup_h = 270
        self.popup_x = (screen_width  - self.popup_w) // 2
        self.popup_y = (screen_height - self.popup_h) // 2
        
    def toggle(self):
        self.visible = not self.visible
        self.restart_requested = False
    
    def handle_event(self, event):
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            
            # 닫기 버튼 (우상단 X)
            close_rect = pygame.Rect(self.popup_x + self.popup_w - 32, self.popup_y + 7, 25, 25)
            if close_rect.collidepoint(mx, my):
                self.visible = False
                return True
            
            # 조류 토글
            bird_rect = pygame.Rect(self.popup_x + 20, self.popup_y + 85, 24, 24)
            if bird_rect.collidepoint(mx, my):
                self.enable_birds = not self.enable_birds
                return True
            
            # 양서류 토글
            amphi_rect = pygame.Rect(self.popup_x + 20, self.popup_y + 135, 24, 24)
            if amphi_rect.collidepoint(mx, my):
                self.enable_amphibians = not self.enable_amphibians
                return True
            
            # 재시작 버튼
            restart_rect = pygame.Rect(self.popup_x + 40, self.popup_y + 200, self.popup_w - 80, 40)
            if restart_rect.collidepoint(mx, my):
                self.restart_options = {
                    'enable_birds': self.enable_birds,
                    'enable_amphibians': self.enable_amphibians,
                }
                self.restart_requested = True
                self.visible = False
                return True
        
        return False
    
    def render(self, screen):
        if not self.visible:
            return
        
        # 반투명 오버레이
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        screen.blit(overlay, (0, 0))
        
        # 팝업 배경
        popup_rect = pygame.Rect(self.popup_x, self.popup_y, self.popup_w, self.popup_h)
        pygame.draw.rect(screen, (28, 32, 42), popup_rect, border_radius=12)
        pygame.draw.rect(screen, (80, 120, 200), popup_rect, 2, border_radius=12)
        
        # 제목
        title = self.font_title.render("재시작 설정", True, (200, 220, 255))
        screen.blit(title, (self.popup_x + 18, self.popup_y + 14))
        
        # 닫기 버튼
        close_rect = pygame.Rect(self.popup_x + self.popup_w - 32, self.popup_y + 7, 25, 25)
        pygame.draw.rect(screen, (180, 60, 60), close_rect, border_radius=5)
        close_txt = self.font_btn.render("X", True, (255, 255, 255))
        screen.blit(close_txt, (close_rect.x + 7, close_rect.y + 4))
        
        # 구분선
        pygame.draw.line(screen, (60, 70, 100),
                         (self.popup_x + 12, self.popup_y + 50),
                         (self.popup_x + self.popup_w - 12, self.popup_y + 50), 1)
        
        desc = self.font_body.render("재시작 시 활성화할 생태계 모드를 선택하세요.", True, (160, 170, 190))
        screen.blit(desc, (self.popup_x + 18, self.popup_y + 58))
        
        # --- 조류 토글 ---
        bird_rect = pygame.Rect(self.popup_x + 20, self.popup_y + 85, 24, 24)
        bird_color = (50, 200, 120) if self.enable_birds else (80, 80, 90)
        pygame.draw.rect(screen, bird_color, bird_rect, border_radius=5)
        if self.enable_birds:
            check = self.font_btn.render("V", True, (255, 255, 255))
            screen.blit(check, (bird_rect.x + 5, bird_rect.y + 3))
        bird_label1 = self.font_body.render("[조류] 초기 3마리 스폰, 비행 사냥 포식자", True, (220, 230, 255))
        screen.blit(bird_label1, (self.popup_x + 52, self.popup_y + 88))
        
        # --- 양서류 토글 ---
        amphi_rect = pygame.Rect(self.popup_x + 20, self.popup_y + 135, 24, 24)
        amphi_color = (50, 180, 200) if self.enable_amphibians else (80, 80, 90)
        pygame.draw.rect(screen, amphi_color, amphi_rect, border_radius=5)
        if self.enable_amphibians:
            check = self.font_btn.render("V", True, (255, 255, 255))
            screen.blit(check, (amphi_rect.x + 5, amphi_rect.y + 3))
        amphi_label1 = self.font_body.render("[양서류] 아종교배 시 50% 확률로 탄생", True, (220, 230, 255))
        screen.blit(amphi_label1, (self.popup_x + 52, self.popup_y + 138))
        amphi_label2 = self.font_body.render("(초기 0마리 / 크기 0.61 이하 / 조류 주요 먹이)", True, (120, 130, 150))
        screen.blit(amphi_label2, (self.popup_x + 52, self.popup_y + 156))
        
        # 재시작 버튼
        btn_rect = pygame.Rect(self.popup_x + 40, self.popup_y + 200, self.popup_w - 80, 40)
        btn_color = (60, 160, 90)
        mx, my = pygame.mouse.get_pos()
        if btn_rect.collidepoint(mx, my):
            btn_color = (80, 200, 110)
        pygame.draw.rect(screen, btn_color, btn_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 220, 140), btn_rect, 2, border_radius=8)
        btn_txt = self.font_btn.render("설정 적용 후 재시작", True, (255, 255, 255))
        tw = btn_txt.get_width()
        screen.blit(btn_txt, (btn_rect.x + (btn_rect.width - tw) // 2, btn_rect.y + 12))
