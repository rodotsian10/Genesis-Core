use pyo3::prelude::*;
use std::sync::Mutex;
use std::sync::OnceLock;

// 러스트 전역 바이옴 맵 캐시 구조체
struct WorldMapCache {
    cols: usize,
    rows: usize,
    tile_size: f64,
    grid: Vec<i64>,
}

static MAP_CACHE: OnceLock<Mutex<Option<WorldMapCache>>> = OnceLock::new();

fn get_map_cache() -> &'static Mutex<Option<WorldMapCache>> {
    MAP_CACHE.get_or_init(|| Mutex::new(None))
}

/// 파이썬에서 생성된 월드맵 데이터를 러스트 캐시에 한 번에 저장합니다.
#[pyfunction]
fn set_world_map(
    cols: usize,
    rows: usize,
    tile_size: f64,
    grid_data: Vec<i64>,
) -> PyResult<()> {
    let mut cache = get_map_cache().lock().unwrap();
    *cache = Some(WorldMapCache {
        cols,
        rows,
        tile_size,
        grid: grid_data,
    });
    Ok(())
}

// 좌표를 기반으로 러스트 메모리에서 직접 바이옴 값을 읽어옵니다.
fn get_biome_at_rust(px: f64, py: f64, cache: &WorldMapCache) -> i64 {
    let tx = (px / cache.tile_size) as usize;
    let ty = (py / cache.tile_size) as usize;
    if tx >= cache.cols || ty >= cache.rows {
        return 0; // 초원 바이옴 기본값 반환 (아웃 오브 바운드 방어)
    }
    cache.grid[tx * cache.rows + ty]
}

/// 러스트 내 바이옴 직접 조회를 이용해 가장 가까운 먹이를 고속 탐색합니다.
#[pyfunction]
fn find_nearest_food(
    animal_x: f64,
    animal_y: f64,
    animal_is_aquatic: bool,
    animal_fur: f64,
    effective_curiosity: f64,
    foods: Vec<(i64, f64, f64, i64)>, // (food_id, fx, fy, food_biome)
) -> PyResult<Option<i64>> {
    let mut nearest_id: Option<i64> = None;
    let mut min_dist_sq = f64::INFINITY;

    let cache_lock = get_map_cache().lock().unwrap();
    let cache = match &*cache_lock {
        Some(c) => c,
        None => return Ok(None), // 캐시가 초기화되지 않았다면 연산 생략
    };

    for (food_id, fx, fy, food_biome) in &foods {
        let dx = animal_x - fx;
        let dy = animal_y - fy;
        let dist_sq = dx * dx + dy * dy;

        if dist_sq >= min_dist_sq {
            continue;
        }

        // 호기심 70% 미만: 바다/육지 경계 밥 제외
        if effective_curiosity < 0.7 {
            let food_in_water = *food_biome == 2 || *food_biome == 4;
            if animal_is_aquatic != food_in_water {
                continue;
            }
        }

        // 호기심 40% 미만: 기온 부적합 지형 밥 제외
        if effective_curiosity < 0.4 {
            if *food_biome == 1 && animal_fur > 0.2 {
                continue;
            }
            if *food_biome == 3 && animal_fur < 0.8 {
                continue;
            }
        }

        // 레이캐스팅 경로 안전성 검사 (4 스텝) - 파이썬 콜백 없이 러스트 단에서 직접 룩업
        let steps = 4;
        let mut path_safe = true;
        for step in 1..steps {
            let t = step as f64 / steps as f64;
            let tx = animal_x + (fx - animal_x) * t;
            let ty = animal_y + (fy - animal_y) * t;
            let tb = get_biome_at_rust(tx, ty, cache);

            if effective_curiosity < 0.7 {
                let waypoint_in_water = tb == 2 || tb == 4;
                if animal_is_aquatic != waypoint_in_water {
                    path_safe = false;
                    break;
                }
            }
            if effective_curiosity < 0.4 {
                if tb == 1 && animal_fur > 0.2 {
                    path_safe = false;
                    break;
                }
                if tb == 3 && animal_fur < 0.8 {
                    path_safe = false;
                    break;
                }
            }
        }

        if !path_safe {
            continue;
        }

        min_dist_sq = dist_sq;
        nearest_id = Some(*food_id);
    }

    Ok(nearest_id)
}

/// 러스트 내 바이옴 직접 조회를 이용해 가장 가까운 짝을 탐색합니다.
#[pyfunction]
fn find_nearest_mate(
    animal_id: i64,
    ax: f64,
    ay: f64,
    animal_is_aquatic: bool,
    animal_fur: f64,
    scan_radius: f64,
    desperate: bool,
    candidates: Vec<(i64, f64, f64, i64, f64, f64, f64)>, // (id, x, y, biome, cooldown, energy, max_energy)
    mated_set: Vec<i64>,
) -> PyResult<Option<(i64, f64)>> {
    let mut nearest_id: Option<i64> = None;
    let mut min_dist = f64::INFINITY;

    let cache_lock = get_map_cache().lock().unwrap();
    let cache = match &*cache_lock {
        Some(c) => c,
        None => return Ok(None),
    };

    for (other_id, ox, oy, biome, cooldown, energy, max_energy) in &candidates {
        if *other_id == animal_id {
            continue;
        }
        if mated_set.contains(other_id) {
            continue;
        }

        if !desperate {
            if (ax - ox).abs() > scan_radius || (ay - oy).abs() > scan_radius {
                continue;
            }

            let mate_in_water = *biome == 2 || *biome == 4;
            if animal_is_aquatic != mate_in_water {
                continue;
            }
            if *biome == 1 && animal_fur > 0.2 {
                continue;
            }
            if *biome == 3 && animal_fur < 0.8 {
                continue;
            }

            // 경로 레이캐스팅 (4 스텝) - 파이썬 콜백 대신 러스트가 직접 룩업
            let steps = 4;
            let mut path_safe = true;
            for step in 1..steps {
                let t = step as f64 / steps as f64;
                let tx = ax + (ox - ax) * t;
                let ty = ay + (oy - ay) * t;
                let tb = get_biome_at_rust(tx, ty, cache);
                let wp_in_water = tb == 2 || tb == 4;
                if animal_is_aquatic != wp_in_water {
                    path_safe = false;
                    break;
                }
                if tb == 1 && animal_fur > 0.2 {
                    path_safe = false;
                    break;
                }
                if tb == 3 && animal_fur < 0.8 {
                    path_safe = false;
                    break;
                }
            }
            if !path_safe {
                continue;
            }
        }

        let req = if desperate { max_energy * 0.3 } else { max_energy * 0.5 };
        if *cooldown > 0.0 || *energy < req {
            continue;
        }

        let dx = ax - ox;
        let dy = ay - oy;
        let dist = (dx * dx + dy * dy).sqrt();

        if dist < min_dist && (desperate || dist < scan_radius) {
            min_dist = dist;
            nearest_id = Some(*other_id);
        }
    }

    Ok(nearest_id.map(|id| (id, min_dist)))
}

#[pyfunction]
fn calc_metabolism(
    biome: i64,
    aquatic_gene: f64,
    fur_gene: f64,
    size_gene: f64,
    speed_gene: f64,
    metabolism_gene: f64,
    current_breath: f64,
    max_breath: f64,
    dt: f64,
) -> PyResult<(f64, f64, f64)> {
    let is_aquatic = aquatic_gene >= 0.5;
    let is_in_water = biome == 2 || biome == 4;

    let new_breath = if aquatic_gene < 0.3 && biome == 4 {
        0.0
    } else if (is_aquatic && !is_in_water) || (!is_aquatic && is_in_water) {
        (current_breath - 10.0 * dt).max(0.0).min(max_breath)
    } else {
        (current_breath + 15.0 * dt).max(0.0).min(max_breath)
    };

    let breath_damage = if new_breath <= 0.0 { 25.0 * dt } else { 0.0 };

    let drain_mult: f64 = match biome {
        1 => {
            if fur_gene <= 0.05 { 2.0 }
            else if fur_gene <= 0.2 { 4.0 }
            else { 4.0 + fur_gene * 16.0 }
        }
        3 => {
            if fur_gene >= 0.95 { 2.0 }
            else if fur_gene >= 0.8 { 4.0 }
            else { 4.0 + (1.0 - fur_gene) * 16.0 }
        }
        _ => 4.0,
    };

    let energy_drain = (size_gene * 0.5 + speed_gene * 1.5) * metabolism_gene * drain_mult * dt / 3.0;

    Ok((new_breath, energy_drain, breath_damage))
}

#[pyfunction]
fn find_nearest_prey(
    bird_x: f64,
    bird_y: f64,
    prey_list: Vec<(i64, f64, f64)>,
) -> PyResult<Option<(i64, f64, f64, f64)>> {
    let mut nearest: Option<(i64, f64, f64, f64)> = None;
    let mut min_dist = f64::INFINITY;

    for (prey_id, px, py) in prey_list {
        let dx = bird_x - px;
        let dy = bird_y - py;
        let dist = (dx * dx + dy * dy).sqrt();

        if dist < min_dist {
            min_dist = dist;
            nearest = Some((prey_id, px, py, dist));
        }
    }

    Ok(nearest)
}

#[pymodule]
fn genesis_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(set_world_map, m)?)?;
    m.add_function(wrap_pyfunction!(find_nearest_food, m)?)?;
    m.add_function(wrap_pyfunction!(find_nearest_mate, m)?)?;
    m.add_function(wrap_pyfunction!(calc_metabolism, m)?)?;
    m.add_function(wrap_pyfunction!(find_nearest_prey, m)?)?;
    Ok(())
}
