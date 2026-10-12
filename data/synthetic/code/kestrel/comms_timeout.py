# DHF-COMPONENT: COMP-06
def overdue(now: float, last: float, timeout: float) -> bool:
    return now - last > timeout
