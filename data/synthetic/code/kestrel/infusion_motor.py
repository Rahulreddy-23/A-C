# DHF-COMPONENT: COMP-02
def pulse_interval(rate: float, pulses_per_ml: int) -> float:
    if rate <= 0 or pulses_per_ml <= 0:
        raise ValueError("Positive rate and calibration required")
    return 3600.0 / (rate * pulses_per_ml)
