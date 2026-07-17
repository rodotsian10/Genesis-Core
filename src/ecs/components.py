from dataclasses import dataclass
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

@dataclass
class DNAComponent:
    size_gene: float
    speed_gene: float
    color_gene: Tuple[int, int, int]
    metabolism_gene: float
    fur_gene: float = 0.5

@dataclass
class FoodComponent:
    energy_value: float
