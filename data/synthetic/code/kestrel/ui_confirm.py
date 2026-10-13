# DHF-COMPONENT: COMP-01
# Implements: SRS-017
def confirm(current: dict, proposed: dict, accepted: bool) -> dict:
    return dict(proposed if accepted else current)
