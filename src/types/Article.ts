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
  additional_context?: string;
  customer_audience?: boolean;
  information_type?: string;
}