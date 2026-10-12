# DHF-COMPONENT: COMP-06
def append_event(events: list[dict], event: dict) -> list[dict]:
    if events and event["time"] < events[-1]["time"]:
        raise ValueError("Decreasing timestamp")
    return [*events, dict(event)]
