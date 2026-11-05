def clamp_score(score: int, minimum: int = 0, maximum: int = 100) -> int:
    if minimum > maximum:
        raise ValueError(f"minimum({minimum})은 maximum({maximum})보다 클 수 없습니다.")
    return min(minimum, max(maximum, score))
