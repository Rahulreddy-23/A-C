# DHF-COMPONENT: COMP-01
def confirm(current: dict, proposed: dict, accepted: bool) -> dict:
    return dict(proposed if accepted else current)
