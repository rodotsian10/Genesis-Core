use pyo3::prelude::*;

/// 월드 맵 바이옴을 조회하기 위한 Python 콜백 함수를 받아
/// 가장 가까운 먹이를 탐색합니다.
///
/// 입력:
///   - animal_x, animal_y: 개체 좌표
///   - animal_is_aquatic: 수생 여부
///   - animal_fur: 털 밀도
///   - effective_curiosity: 유효 호기심 (0.0 ~ 1.0)
///   - foods: (food_id, fx, fy, biome, is_dead) 리스트
///   - get_biome: (x, y) -> biome_int Python 콜백
///
/// 반환: 가장 가까운 food_id (없으면 None)
#[pyfunction]
fn find_nearest_food(
    animal_x: f64,
    animal_y: f64,
    animal_is_aquatic: bool,
    animal_fur: f64,
    effective_curiosity: f64,
    foods: Vec<(i64, f64, f64, i64)>, // (food_id, fx, fy, food_biome)
    py: Python<'_>,
    get_biome_callback: PyObject, // Python callable: (x: f64, y: f64) -> i64
) -> PyResult<Option<i64>> {
    let mut nearest_id: Option<i64> = None;
    let mut min_dist_sq = f64::INFINITY;

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
                continue; // 사막인데 털 많음
            }
            if *food_biome == 3 && animal_fur < 0.8 {
                continue; // 설원인데 털 얇음
            }
        }

        // 레이캐스팅 경로 안전성 검사 (4 스텝)
        let steps = 4;
        let mut path_safe = true;
        for step in 1..steps {
            let t = step as f64 / steps as f64;
            let tx = animal_x + (fx - animal_x) * t;
            let ty = animal_y + (fy - animal_y) * t;
            let tb: i64 = get_biome_callback.call1(py, (tx, ty))?.extract(py)?;

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

/// 가장 가까운 번식 가능한 짝을 탐색합니다.
///
/// 입력:
///   - animal_id: 현 개체 ID
///   - ax, ay: 현 개체 좌표
///   - animal_is_aquatic: 수생 여부
///   - animal_fur: 털 밀도
///   - scan_radius: 탐색 반경
///   - desperate: 최후의 번식 모드 여부
///   - candidates: (other_id, ox, oy, biome, cooldown, energy, max_energy) 리스트
///   - get_biome_callback: Python callable (x, y) -> biome_int
///
/// 반환: (nearest_mate_id, distance) 또는 None
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
    py: Python<'_>,
    get_biome_callback: PyObject,
) -> PyResult<Option<(i64, f64)>> {
    let mut nearest_id: Option<i64> = None;
    let mut min_dist = f64::INFINITY;

    for (other_id, ox, oy, biome, cooldown, energy, max_energy) in &candidates {
        if *other_id == animal_id {
            continue;
        }
        if mated_set.contains(other_id) {
            continue;
        }

        // desperate가 아닐 때만 범위 및 지형 제한 적용
        if !desperate {
            if (ax - ox).abs() > scan_radius || (ay - oy).abs() > scan_radius {
                continue;
            }

            // 짝 위치가 안전 지형인지 확인
            let mate_in_water = *biome == 2 || *biome == 4;
            if animal_is_aquatic != mate_in_water {
                continue;
            }
            // 털 기온 적합성
            if *biome == 1 && animal_fur > 0.2 {
                continue;
            }
            if *biome == 3 && animal_fur < 0.8 {
                continue;
            }

            // 경로 레이캐스팅 (4 스텝)
            let steps = 4;
            let mut path_safe = true;
            for step in 1..steps {
                let t = step as f64 / steps as f64;
                let tx = ax + (ox - ax) * t;
                let ty = ay + (oy - ay) * t;
                let tb: i64 = get_biome_callback.call1(py, (tx, ty))?.extract(py)?;
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

        // 짝의 번식 가능 여부 확인
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

/// 개체의 메타볼리즘(호흡, 기력 소모)을 한꺼번에 계산해 반환합니다.
///
/// 반환: (new_breath, energy_drain, breath_damage)
///   - new_breath: 업데이트 된 호흡량
///   - energy_drain: 이번 프레임 에너지 소모량
///   - breath_damage: 이번 프레임 호흡 고갈로 인한 체력 피해
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

    // 호흡 계산
    let new_breath = if aquatic_gene < 0.3 && biome == 4 {
        // 친수성 30% 미만이 깊은 물 → 즉시 질식
        0.0
    } else if (is_aquatic && !is_in_water) || (!is_aquatic && is_in_water) {
        (current_breath - 10.0 * dt).max(0.0).min(max_breath)
    } else {
        (current_breath + 15.0 * dt).max(0.0).min(max_breath)
    };

    let breath_damage = if new_breath <= 0.0 { 25.0 * dt } else { 0.0 };

    // 기력 소모 계산 (지형 드레인 배율)
    let drain_mult: f64 = match biome {
        1 => {
            // 사막
            if fur_gene <= 0.05 { 2.0 }
            else if fur_gene <= 0.2 { 4.0 }
            else { 4.0 + fur_gene * 16.0 }
        }
        3 => {
            // 설원
            if fur_gene >= 0.95 { 2.0 }
            else if fur_gene >= 0.8 { 4.0 }
            else { 4.0 + (1.0 - fur_gene) * 16.0 }
        }
        _ => 4.0,
    };

    let energy_drain = (size_gene * 0.5 + speed_gene * 1.5) * metabolism_gene * drain_mult * dt / 3.0;

    Ok((new_breath, energy_drain, breath_damage))
}

/// PyO3 모듈 등록
#[pymodule]
fn genesis_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(find_nearest_food, m)?)?;
    m.add_function(wrap_pyfunction!(find_nearest_mate, m)?)?;
    m.add_function(wrap_pyfunction!(calc_metabolism, m)?)?;
    Ok(())
}
