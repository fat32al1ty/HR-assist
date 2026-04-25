export interface TrackGapItem {
  skill: string;
  fraction: number;
  vacancies_with_gap_count: number;
}

export interface TrackGapBlock {
  track: 'match' | 'grow' | 'stretch';
  vacancies_count: number;
  top_gaps: TrackGapItem[];
  softer_subset_count: number;
}

export interface TrackGapAnalysisOut {
  match: TrackGapBlock;
  grow: TrackGapBlock;
  stretch: TrackGapBlock;
}
