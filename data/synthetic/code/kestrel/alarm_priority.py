# DHF-COMPONENT: COMP-04
def highest(alarms: list[dict]) -> dict | None:
    return max(alarms, key=lambda a: a["priority"], default=None)
