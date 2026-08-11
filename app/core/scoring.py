def clamp_score(score: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, score))
