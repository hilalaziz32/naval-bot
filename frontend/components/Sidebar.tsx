'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, MessageSquare, Trash2, LogOut, Book } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { getConversations, deleteConversation, getBooks } from '@/lib/api'
import type { Conversation, Book as BookType } from '@/lib/types'

interface SidebarProps {
  currentConversationId?: string
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  selectedBook?: string
  onBookChange: (book?: string) => void
}

export default function Sidebar({
  currentConversationId,
  onNewChat,
  onSelectConversation,
  selectedBook,
  onBookChange,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [books, setBooks] = useState<BookType[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [convs, bks] = await Promise.all([
        getConversations(),
        getBooks(),
      ])
      setConversations(convs)
      setBooks(bks)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return

    try {
      await deleteConversation(id)
      setConversations(conversations.filter((c) => c.id !== id))
      if (currentConversationId === id) {
        onNewChat()
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    }
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="w-80 h-screen bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-800">
        <h1 className="text-xl font-bold text-white mb-4">Navy Watch</h1>
        
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition font-medium"
        >
          <Plus className="w-5 h-5" />
          New Chat
        </button>
      </div>

      {/* Book Selector */}
      <div className="p-4 border-b border-slate-800">
        <label className="block text-xs font-medium text-slate-400 mb-2">
          <Book className="w-3 h-3 inline mr-1" />
          Search Scope
        </label>
        <select
          value={selectedBook || ''}
          onChange={(e) => onBookChange(e.target.value || undefined)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All books (auto-route)</option>
          {books.map((book) => (
            <option key={book.source_file} value={book.source_file}>
              {book.short_title || book.title || book.source_file}
            </option>
          ))}
        </select>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {loading ? (
          <div className="text-center text-slate-500 text-sm py-8">
            Loading...
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center text-slate-500 text-sm py-8">
            No conversations yet
          </div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className={`group relative p-3 rounded-lg cursor-pointer transition ${
                currentConversationId === conv.id
                  ? 'bg-slate-800 border border-slate-700'
                  : 'hover:bg-slate-800/50'
              }`}
            >
              <div className="flex items-start gap-3">
                <MessageSquare className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate font-medium">
                    {conv.title}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    {formatDate(conv.created_at)}
                  </p>
                </div>
                <button
                  onClick={(e) => handleDelete(conv.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded transition"
                >
                  <Trash2 className="w-4 h-4 text-red-400" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800">
        <button
          onClick={handleSignOut}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition text-sm"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </div>
  )
}
