export interface Article {
  title: string;
  date: string;
  excerpt: string;
  slug: string;
  topic: string;
  tags: string[];
  content: string;
}

export interface ArticleInput {
  topic: string;
  additionalContext?: string;
}