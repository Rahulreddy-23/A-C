# DHF-COMPONENT: COMP-05
# Implements: SRS-007, SRS-018
import math
from dataclasses import dataclass


def valid_dose(dose: float, minimum: float, maximum: float) -> bool:
    return minimum <= dose <= maximum


@dataclass(frozen=True)
class DrugLimits:
    key: str
    minimum_dose: float
    maximum_dose: float
    concentration: float

    def validate(self) -> None:
        if not self.key or not all(
            math.isfinite(v) for v in (self.minimum_dose, self.maximum_dose, self.concentration)
        ):
            raise ValueError("Invalid drug limits")
        if (
            self.minimum_dose < 0
            or self.maximum_dose < self.minimum_dose
            or self.concentration <= 0
        ):
            raise ValueError("Inconsistent drug limits")


class DoseValidator:
    """Validate library bounds before allowing dose-to-volume conversion."""

    def __init__(self, limits: DrugLimits):
        limits.validate()
        self.limits = limits

    def volume_for(self, dose: float) -> float:
        if not math.isfinite(dose):
            raise ValueError("Invalid dose")
        if not valid_dose(dose, self.limits.minimum_dose, self.limits.maximum_dose):
            raise ValueError("Dose outside validated library bounds")
        return dose / self.limits.concentration

    def check_proposal(self, proposal: dict) -> dict:
        if proposal.get("drug") != self.limits.key:
            raise ValueError("Drug record mismatch")
        if "dose" not in proposal:
            raise ValueError("Dose required")
        return {
            "drug": self.limits.key,
            "dose": proposal["dose"],
            "volume_ml": self.volume_for(proposal["dose"]),
        }
