import { createClient } from '@/lib/supabase/client'
import type { Conversation, Message, Book, StreamEvent } from './types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function getAuthHeaders() {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  
  if (!session?.access_token) {
    throw new Error('Not authenticated')
  }
  
  return {
    'Authorization': `Bearer ${session.access_token}`,
    'Content-Type': 'application/json',
  }
}

export async function getBooks(): Promise<Book[]> {
  const response = await fetch(`${API_URL}/api/books`)
  const data = await response.json()
  return data.books
}

export async function getConversations(): Promise<Conversation[]> {
  const headers = await getAuthHeaders()
  const response = await fetch(`${API_URL}/api/conversations`, { headers })
  
  if (!response.ok) {
    throw new Error('Failed to fetch conversations')
  }
  
  return response.json()
}

export async function getMessages(conversationId: string): Promise<Message[]> {
  const headers = await getAuthHeaders()
  const response = await fetch(
    `${API_URL}/api/conversations/${conversationId}/messages`,
    { headers }
  )
  
  if (!response.ok) {
    throw new Error('Failed to fetch messages')
  }
  
  return response.json()
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const headers = await getAuthHeaders()
  const response = await fetch(
    `${API_URL}/api/conversations/${conversationId}`,
    {
      method: 'DELETE',
      headers,
    }
  )
  
  if (!response.ok) {
    throw new Error('Failed to delete conversation')
  }
}

export async function* streamChat(
  message: string,
  conversationId?: string,
  bookLock?: string,
  topK: number = 6
): AsyncGenerator<StreamEvent> {
  const headers = await getAuthHeaders()
  
  const response = await fetch(`${API_URL}/api/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      book_lock: bookLock,
      top_k: topK,
    }),
  })
  
  if (!response.ok) {
    let detail = ''
    try {
      const data = await response.json()
      detail = data?.detail ? String(data.detail) : ''
    } catch {
      // ignore parse errors
    }

    if (response.status === 401) {
      throw new Error(detail || 'Unauthorized. Please sign in again.')
    }

    throw new Error(detail || `Failed to send message (HTTP ${response.status})`)
  }
  
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }
  
  const decoder = new TextDecoder()
  let buffer = ''
  let sawDone = false
  
  try {
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      
      // Process complete SSE messages
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          try {
            const event: StreamEvent = JSON.parse(data)
            if (event.type === 'done') {
              sawDone = true
            }
            yield event
          } catch (e) {
            console.error('Failed to parse SSE data:', data)
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
    if (!sawDone) {
      yield { type: 'done' }
    }
  }
}
