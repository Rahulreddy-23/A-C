# DHF-COMPONENT: COMP-01
# Implements: SRS-001, SRS-007, SRS-013, SRS-019, SRS-025, SRS-031
def confirm(current: dict, proposed: dict, accepted: bool) -> dict:
    return dict(proposed if accepted else current)
