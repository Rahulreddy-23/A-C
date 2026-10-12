# DHF-COMPONENT: COMP-05
def lookup(library: dict, key: str) -> dict:
    if key not in library:
        raise KeyError(key)
    return dict(library[key])
