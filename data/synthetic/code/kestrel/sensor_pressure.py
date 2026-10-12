# DHF-COMPONENT: COMP-03
def occluded(pressure: float, threshold: float = 80.0) -> bool:
    if pressure < 0:
        raise ValueError("Invalid pressure")
    return pressure > threshold
