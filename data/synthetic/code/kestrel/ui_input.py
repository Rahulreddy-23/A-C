# DHF-COMPONENT: COMP-01
# Implements: SRS-016
def parse_rate(value: str, maximum: float) -> float:
    rate = float(value)
    if not 0 < rate <= maximum:
        raise ValueError("Invalid rate")
    return rate
