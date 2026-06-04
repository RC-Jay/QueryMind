from pydantic import BaseModel


class KPIItem(BaseModel):
    label: str
    value: str
    icon: str = ""


class KPISnapshotOut(BaseModel):
    kpis: list[KPIItem]
