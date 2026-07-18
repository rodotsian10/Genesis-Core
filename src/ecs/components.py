from dataclasses import dataclass, field
from typing import Tuple

@dataclass
class PositionComponent:
    x: float
    y: float
    wander_angle: float = 0.0
    wander_timer: float = 0.0
    blocked_timer: float = 0.0

@dataclass
class RenderComponent:
    color: Tuple[int, int, int]
    size: int

@dataclass
class HealthComponent:
    current_health: float
    max_health: float
    age: float = 0.0
    lifespan: float = 100.0
    energy: float = 100.0
    max_energy: float = 100.0
    mating_cooldown: float = 0.0
    breath: float = 100.0
    max_breath: float = 100.0
    mated_count: int = 0

@dataclass
class DNAComponent:
    size_gene: float
    speed_gene: float
    color_gene: Tuple[int, int, int]
    metabolism_gene: float
    fur_gene: float = 0.5
    aquatic_gene: float = 0.0   # 0.0=완전 육지, 1.0=완전 수생
    curiosity_gene: float = 0.5 # 0.0=겁쟁이, 1.0=무모한 탐험가
    generation: int = 1         # 개체 세대 계보
    is_mutated: bool = False    # 돌연변이 여부 표시
    mutated_features: dict = field(default_factory=dict) # 어떤 스탯에 얼마나 돌연변이가 발생했는지 저장
    is_bird: bool = False       # 조류 여부
    is_egg: bool = False        # 알 상태 여부
    egg_timer: float = 0.0      # 알 부화 타이머 (30초에 부화)
    is_amphibian: bool = False  # 양서류 여부





@dataclass
class FoodComponent:
    energy_value: float
    age: float = 0.0
    is_seaweed: bool = False
    is_wilted: bool = False
