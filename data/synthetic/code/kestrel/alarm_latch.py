# DHF-COMPONENT: COMP-04
def latched(active: bool, acknowledged: bool, unsafe: bool) -> bool:
    return unsafe or (active and not acknowledged)
