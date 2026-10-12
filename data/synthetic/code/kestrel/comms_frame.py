# DHF-COMPONENT: COMP-06
def valid_frame(payload: bytes) -> bool:
    return payload.startswith(b"KIC:") and payload.endswith(b"\n")
