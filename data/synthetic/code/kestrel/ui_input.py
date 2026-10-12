# DHF-COMPONENT: COMP-01
# Implements: SRS-001, SRS-007, SRS-013, SRS-019, SRS-025, SRS-031
def parse_rate(value: str, maximum: float) -> float:
    rate = float(value)
    if not 0 < rate <= maximum:
        raise ValueError("Invalid rate")
    return rate
