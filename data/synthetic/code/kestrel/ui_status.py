# DHF-COMPONENT: COMP-01
# Implements: SRS-015, SRS-032
def status(mode: str, volume: float) -> dict:
    return {"mode": mode, "delivered_ml": max(0.0, volume)}
