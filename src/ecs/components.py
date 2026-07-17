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

@dataclass
class FoodComponent:
    energy_value: float
    age: float = 0.0
    is_seaweed: bool = False
    is_wilted: bool = False
