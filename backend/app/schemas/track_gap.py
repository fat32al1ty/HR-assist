from typing import Literal

from pydantic import BaseModel


class TrackGapItem(BaseModel):
    skill: str
    fraction: float
    vacancies_with_gap_count: int


class TrackGapBlock(BaseModel):
    track: Literal["match", "grow", "stretch"]
    vacancies_count: int
    top_gaps: list[TrackGapItem]
    softer_subset_count: int


class TrackGapAnalysisOut(BaseModel):
    match: TrackGapBlock
    grow: TrackGapBlock
    stretch: TrackGapBlock
