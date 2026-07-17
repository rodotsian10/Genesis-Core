class Camera:
    def __init__(self, width, height, world_width, world_height):
        self.width = width
        self.height = height
        self.camera_rect = [0, 0, width, height] # x, y, w, h
        self.world_width = world_width
        self.world_height = world_height
        self.zoom = 1.0
        self.target_entity = None
        self.world = None

    def set_target(self, entity, world):
        self.target_entity = entity
        self.world = world

    def clear_target(self):
        self.target_entity = None

    def update(self):
        if self.target_entity is not None and self.world is not None:
            # ecs_components의 순환참조 방지를 위해 로컬 import
            from ecs.components import PositionComponent
            if self.target_entity in self.world.entities:
                pos = self.world.get_component(self.target_entity, PositionComponent)
                if pos:
                    target_cam_x = pos.x - (self.width / (2 * self.zoom))
                    target_cam_y = pos.y - (self.height / (2 * self.zoom))
                    
                    # 부드러운 카메라 이동 (Lerp)
                    self.camera_rect[0] += (target_cam_x - self.camera_rect[0]) * 0.1
                    self.camera_rect[1] += (target_cam_y - self.camera_rect[1]) * 0.1
                    self._keep_in_bounds()
            else:
                self.clear_target() # 타겟 사망 시 추적 해제

    def apply(self, entity_x, entity_y):
        screen_x = (entity_x - self.camera_rect[0]) * self.zoom
        screen_y = (entity_y - self.camera_rect[1]) * self.zoom
        return screen_x, screen_y
        
    def apply_size(self, size):
        return max(1, int(size * self.zoom))

    def focus_on(self, x, y):
        self.clear_target()
        self.camera_rect[0] = x - (self.width / (2 * self.zoom))
        self.camera_rect[1] = y - (self.height / (2 * self.zoom))
        self._keep_in_bounds()

    def screen_to_world(self, screen_x, screen_y):
        world_x = (screen_x / self.zoom) + self.camera_rect[0]
        world_y = (screen_y / self.zoom) + self.camera_rect[1]
        return world_x, world_y

    def handle_input(self, dx, dy):
        self.clear_target() # 수동 드래그 조작 시 추적 풀림
        self.camera_rect[0] -= dx / self.zoom
        self.camera_rect[1] -= dy / self.zoom
        self._keep_in_bounds()

    def handle_zoom(self, zoom_amount, mouse_x, mouse_y):
        world_x_before, world_y_before = self.screen_to_world(mouse_x, mouse_y)
        
        self.zoom += zoom_amount
        self.zoom = max(0.2, min(self.zoom, 5.0))
        
        world_x_after, world_y_after = self.screen_to_world(mouse_x, mouse_y)
        
        self.camera_rect[0] += world_x_before - world_x_after
        self.camera_rect[1] += world_y_before - world_y_after
        self._keep_in_bounds()

    def _keep_in_bounds(self):
        if self.camera_rect[0] < -500: self.camera_rect[0] = -500
        if self.camera_rect[1] < -500: self.camera_rect[1] = -500
        if self.camera_rect[0] > self.world_width + 500: self.camera_rect[0] = self.world_width + 500
        if self.camera_rect[1] > self.world_height + 500: self.camera_rect[1] = self.world_height + 500
