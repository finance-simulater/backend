def clamp_score(score: int, minimum: int = 0, maximum: int = 100) -> int:
    if minimum > maximum:
        raise ValueError(
            f"minimum must be less than or equal to maximum (got minimum={minimum}, maximum={maximum})"
        )
    return max(minimum, min(maximum, score))
