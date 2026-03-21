'use client'

import { useState, useEffect, useRef } from 'react'
import { Send, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Sidebar from '@/components/Sidebar'
import ChatMessage from '@/components/ChatMessage'
import { streamChat, getMessages } from '@/lib/api'
import type { Message, Citation, EvidenceCard } from '@/lib/types'
import { normalizeMarkdown } from '@/lib/markdown'

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState<string>()
  const [selectedBook, setSelectedBook] = useState<string>()
  const [streamingMessage, setStreamingMessage] = useState('')
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([])
  const [streamingEvidence, setStreamingEvidence] = useState<EvidenceCard[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingMessage])

  const loadConversation = async (conversationId: string) => {
    try {
      const msgs = await getMessages(conversationId)
      setMessages(msgs)
      setCurrentConversationId(conversationId)
      setStreamingMessage('')
    } catch (error) {
      console.error('Failed to load conversation:', error)
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setCurrentConversationId(undefined)
    setSelectedBook(undefined)
    setStreamingMessage('')
    setInput('')
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setLoading(true)
    setStreamingMessage('')
    setStreamingCitations([])
    setStreamingEvidence([])

    // Add user message to UI immediately
    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: currentConversationId || '',
      role: 'user',
      content: userMessage,
      citations: [],
      evidence_cards: [],
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, tempUserMessage])

    try {
      let accumulatedContent = ''
      let finalCitations: Citation[] = []
      let finalEvidence: EvidenceCard[] = []
      let newConversationId = currentConversationId

      for await (const event of streamChat(
        userMessage,
        currentConversationId,
        selectedBook
      )) {
        if (event.type === 'token' && event.content) {
          accumulatedContent += event.content
          setStreamingMessage(accumulatedContent)
        } else if (event.type === 'metadata') {
          finalCitations = event.citations || []
          finalEvidence = event.evidence_cards || []
          setStreamingCitations(finalCitations)
          setStreamingEvidence(finalEvidence)
        } else if (event.type === 'done') {
          const safeContent = accumulatedContent.trim()
          // Message is complete, add to messages list
          const assistantMessage: Message = {
            id: `msg-${Date.now()}`,
            conversation_id: newConversationId || '',
            role: 'assistant',
            content: safeContent || 'I could not generate an answer. Please try again.',
            citations: finalCitations,
            evidence_cards: finalEvidence,
            created_at: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, assistantMessage])
          setStreamingMessage('')
          
          // If this was a new conversation, we should reload to get the conversation ID
          if (!currentConversationId) {
            // The backend creates the conversation, we'll get it on next load
            // For now, just keep the messages in state
          }
        } else if (event.type === 'error') {
          const errorText = event.message || 'Failed to generate answer.'
          console.error('Stream error:', errorText)
          setStreamingMessage('')
          setMessages((prev) => [
            ...prev,
            {
              id: `err-${Date.now()}`,
              conversation_id: newConversationId || '',
              role: 'assistant',
              content: `I couldn't generate an answer: ${errorText}`,
              citations: [],
              evidence_cards: [],
              created_at: new Date().toISOString(),
            },
          ])
          break
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      const message = error instanceof Error ? error.message : 'Failed to send message'

      if (message.toLowerCase().includes('unauthorized') || message.toLowerCase().includes('sign in')) {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            conversation_id: currentConversationId || '',
            role: 'assistant',
            content: 'Your session expired. Please sign in again to continue.',
            citations: [],
            evidence_cards: [],
            created_at: new Date().toISOString(),
          },
        ])
        window.location.href = '/login'
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            conversation_id: currentConversationId || '',
            role: 'assistant',
            content: `I couldn't generate an answer: ${message}`,
            citations: [],
            evidence_cards: [],
            created_at: new Date().toISOString(),
          },
        ])
      }
      setStreamingMessage('')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex h-screen bg-slate-950">
      <Sidebar
        currentConversationId={currentConversationId}
        onNewChat={handleNewChat}
        onSelectConversation={loadConversation}
        selectedBook={selectedBook}
        onBookChange={setSelectedBook}
      />

      <div className="flex-1 flex flex-col">
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            {messages.length === 0 && !streamingMessage && (
              <div className="text-center py-20">
                <h2 className="text-4xl font-bold text-white mb-4">
                  Evening, Navy Watch
                </h2>
                <p className="text-slate-400 text-lg">
                  Ask me anything about Royal Navy seamanship, navigation, and regulations.
                </p>
              </div>
            )}

            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {/* Streaming message */}
            {streamingMessage && (
              <div className="flex justify-start mb-6">
                <div className="max-w-3xl w-full">
                  <div className="rounded-2xl px-6 py-4 bg-slate-800/50 border border-slate-700/50 text-slate-100">
                    <div className="chat-markdown">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {normalizeMarkdown(streamingMessage)}
                      </ReactMarkdown>
                      <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
                    </div>
                  </div>
                  {streamingCitations.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {streamingCitations.map((citation) => (
                        <div
                          key={citation.idx}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/50 border border-slate-700/50 rounded-lg text-xs text-slate-300"
                        >
                          <span className="font-medium">[{citation.idx}]</span>
                          <span className="text-slate-400">
                            {citation.source_file}
                            {citation.page_start && ` p.${citation.page_start}`}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-800 bg-slate-900/50 backdrop-blur-xl">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about naval procedures, navigation, or regulations..."
                disabled={loading}
                rows={1}
                className="w-full px-4 py-3 pr-12 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  minHeight: '52px',
                  maxHeight: '200px',
                }}
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="absolute right-2 bottom-2 p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-lg transition"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-2 text-center">
              Press Enter to send, Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
