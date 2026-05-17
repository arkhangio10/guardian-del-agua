from pydantic import BaseModel


class Operator(BaseModel):
    operator_name: str
    concession_id: str
    osinergmin_id: str
    prior_sanctions: int
    legal_status: str
    parent_company: str
    total_spills: int = 0
    total_volume_barrels: int = 0
    open_sanctions: int = 0


class LeaderboardEntry(BaseModel):
    rank: int
    operator_name: str
    total_spills: int
    total_volume_barrels: int
    open_sanctions: int
    legal_status: str
