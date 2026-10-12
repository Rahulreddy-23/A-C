# DHF-COMPONENT: COMP-03
def average(samples: list[float]) -> float:
    if not samples:
        raise ValueError("No samples")
    return sum(samples) / len(samples)
