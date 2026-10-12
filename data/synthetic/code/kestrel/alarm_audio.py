# DHF-COMPONENT: COMP-04
def audible(critical: bool, muted: bool) -> bool:
    return critical and not muted
