export interface CachedImage {
  url: string;
  tags: string[];
  clip_score: number;
  used: boolean;
  section?: string;
}

export interface ImageValidationResult {
  url: string;
  clip_score: number;
  tags: string[];
  section?: string;
  approved: boolean;
}
