export interface Book {
  source_file: string
  title: string
  short_title?: string
  summary: string
  aliases: string[]
}

export interface Citation {
  idx: number
  source_file: string
  page_start?: number
  line_start?: number
}

export interface EvidenceCard {
  citation_idx: number
  source_file: string
  page_start?: number
  line_start?: number
  similarity: number
  excerpt: string
  why_selected: string[]
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  evidence_cards: EvidenceCard[]
  created_at: string
}

export interface Conversation {
  id: string
  user_id: string
  title: string
  book_lock?: string
  created_at: string
  updated_at: string
}

export interface StreamEvent {
  type: 'token' | 'metadata' | 'done' | 'error'
  content?: string
  citations?: Citation[]
  evidence_cards?: EvidenceCard[]
  message?: string
}
