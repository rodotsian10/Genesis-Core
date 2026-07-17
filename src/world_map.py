import math
import random
import pygame

class Biome:
    GRASS = 0
    DESERT = 1
    WATER = 2
    SNOW = 3
    DEEP_WATER = 4 # 진한 바다/강/호수

class ValueNoise:
    def __init__(self, seed=None):
        if seed is not None:
            random.seed(seed)
        self.grid = {}

    def get_val(self, ix, iy):
        if (ix, iy) not in self.grid:
            self.grid[(ix, iy)] = random.random()
        return self.grid[(ix, iy)]

    def noise2d(self, x, y):
        ix = math.floor(x)
        iy = math.floor(y)
        fx = x - ix
        fy = y - iy

        # Smoothstep (부드러운 보간)
        ux = fx * fx * (3.0 - 2.0 * fx)
        uy = fy * fy * (3.0 - 2.0 * fy)

        v00 = self.get_val(ix, iy)
        v10 = self.get_val(ix + 1, iy)
        v01 = self.get_val(ix, iy + 1)
        v11 = self.get_val(ix + 1, iy + 1)

        nx0 = v00 * (1.0 - ux) + v10 * ux
        nx1 = v01 * (1.0 - ux) + v11 * ux
        return nx0 * (1.0 - uy) + nx1 * uy

    def fractal_noise(self, x, y, octaves=4, persistence=0.5, lacunarity=2.0):
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0
        for _ in range(octaves):
            total += self.noise2d(x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= lacunarity
        return total / max_value

class WorldMap:
    def __init__(self, width_px, height_px, tile_size=40):
        self.tile_size = tile_size
        self.cols = int(width_px / tile_size)
        self.rows = int(height_px / tile_size)
        self.grid = [[Biome.GRASS for _ in range(self.rows)] for _ in range(self.cols)]
        self._generate_terrain()
        self._cache_surfaces()

    def _generate_terrain(self):
        # 자연스러운 대륙과 호수를 위한 2D 프랙탈 노이즈 (리본 현상 제거)
        elevation_noise = ValueNoise(seed=random.randint(0, 99999))
        temperature_noise = ValueNoise(seed=random.randint(0, 99999))
        
        for x in range(self.cols):
            for y in range(self.rows):
                # 높이맵 (0.0 ~ 1.0)
                elevation = elevation_noise.fractal_noise(x * 0.08, y * 0.08, octaves=4)
                # 온도맵 (0.0 ~ 1.0)
                temperature = temperature_noise.fractal_noise(x * 0.05, y * 0.05, octaves=3)
                
                # 고도가 낮을수록 깊은 물
                if elevation < 0.35:
                    self.grid[x][y] = Biome.DEEP_WATER
                elif elevation < 0.45:
                    self.grid[x][y] = Biome.WATER # 얕은 물결
                else:
                    if temperature > 0.65:
                        self.grid[x][y] = Biome.DESERT
                    elif temperature < 0.35:
                        self.grid[x][y] = Biome.SNOW
                    else:
                        self.grid[x][y] = Biome.GRASS

    def _cache_surfaces(self):
        # 스타듀밸리 감성의 톤다운된 지형 색상
        self.colors = {
            Biome.GRASS: (100, 160, 80),
            Biome.DESERT: (220, 190, 120),
            Biome.WATER: (70, 140, 200),
            Biome.DEEP_WATER: (40, 100, 160), # 진한 호수/강/바다
            Biome.SNOW: (230, 240, 250)
        }

    def get_biome_at(self, px, py):
        tx = int(px / self.tile_size)
        ty = int(py / self.tile_size)
        if tx < 0: tx = 0
        if ty < 0: ty = 0
        if tx >= self.cols: tx = self.cols - 1
        if ty >= self.rows: ty = self.rows - 1
        return self.grid[tx][ty]

    def render(self, screen, camera):
        world_left, world_top = camera.screen_to_world(0, 0)
        world_right, world_bottom = camera.screen_to_world(screen.get_width(), screen.get_height())
        
        start_tx = max(0, int(world_left / self.tile_size))
        start_ty = max(0, int(world_top / self.tile_size))
        end_tx = min(self.cols, int(world_right / self.tile_size) + 1)
        end_ty = min(self.rows, int(world_bottom / self.tile_size) + 1)
        
        # 타일 간 미세한 빈틈이 생기는 것을 막기 위해 크기를 올림 처리
        screen_tile_size = math.ceil(self.tile_size * camera.zoom)
        
        for x in range(start_tx, end_tx):
            for y in range(start_ty, end_ty):
                biome = self.grid[x][y]
                color = self.colors[biome]
                
                px = x * self.tile_size
                py = y * self.tile_size
                
                sx, sy = camera.apply(px, py)
                rect = pygame.Rect(int(sx), int(sy), screen_tile_size + 1, screen_tile_size + 1)
                pygame.draw.rect(screen, color, rect)
