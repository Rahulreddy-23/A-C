# DHF-COMPONENT: COMP-06
# Implements: (unallocated)
def diagnostic_summary(values: list[float]) -> dict:
    return {"count": len(values), "maximum": max(values, default=0.0)}
