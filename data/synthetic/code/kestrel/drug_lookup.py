# DHF-COMPONENT: COMP-05
# Implements: SRS-019, SRS-020
def lookup(library: dict, key: str) -> dict:
    if key not in library:
        raise KeyError(key)
    return dict(library[key])


class DrugLibrary:
    """Copy validated records into an isolated lookup snapshot."""

    def __init__(self, records: dict) -> None:
        self.records: dict[str, dict] = {}
        for key, record in records.items():
            if not key or "minimum" not in record or "maximum" not in record:
                raise ValueError("Incomplete drug record")
            if record["minimum"] < 0 or record["maximum"] < record["minimum"]:
                raise ValueError("Invalid drug bounds")
            self.records[key] = dict(record)

    def get(self, key: str) -> dict:
        return lookup(self.records, key)

    def keys(self) -> list[str]:
        return sorted(self.records)

    def select(self, key: str, dose: float) -> dict:
        record = self.get(key)
        if not record["minimum"] <= dose <= record["maximum"]:
            raise ValueError("Dose outside selected drug limits")
        return {"drug": key, "dose": dose, "limits": record}
