# DHF-COMPONENT: COMP-01
# Implements: SRS-001, SRS-007, SRS-013, SRS-019, SRS-025, SRS-031
def status(mode: str, volume: float) -> dict:
    return {"mode": mode, "delivered_ml": max(0.0, volume)}
