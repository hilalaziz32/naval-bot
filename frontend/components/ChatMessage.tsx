'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '@/lib/types'
import { ChevronDown, ChevronUp, FileText } from 'lucide-react'
import { normalizeMarkdown } from '@/lib/markdown'

interface ChatMessageProps {
  message: Message
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const [showEvidence, setShowEvidence] = useState(false)
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className={`max-w-3xl ${isUser ? 'w-auto' : 'w-full'}`}>
        <div
          className={`rounded-2xl px-6 py-4 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-slate-800/50 border border-slate-700/50 text-slate-100'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="chat-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => <h1>{children}</h1>,
                  h2: ({ children }) => <h2>{children}</h2>,
                  h3: ({ children }) => <h3>{children}</h3>,
                  h4: ({ children }) => <h4>{children}</h4>,
                  p: ({ children }) => <p>{children}</p>,
                  ul: ({ children }) => <ul>{children}</ul>,
                  ol: ({ children }) => <ol>{children}</ol>,
                  li: ({ children }) => <li>{children}</li>,
                  blockquote: ({ children }) => <blockquote>{children}</blockquote>,
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                  code: ({ inline, children }: any) =>
                    inline ? <code>{children}</code> : <code>{children}</code>,
                  pre: ({ children }) => <pre>{children}</pre>,
                  table: ({ children }) => <table>{children}</table>,
                  thead: ({ children }) => <thead>{children}</thead>,
                  tbody: ({ children }) => <tbody>{children}</tbody>,
                  tr: ({ children }) => <tr>{children}</tr>,
                  th: ({ children }) => <th>{children}</th>,
                  td: ({ children }) => <td>{children}</td>,
                }}
              >
                {normalizeMarkdown(message.content)}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.citations.map((citation) => (
              <div
                key={citation.idx}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/50 border border-slate-700/50 rounded-lg text-xs text-slate-300"
              >
                <FileText className="w-3 h-3" />
                <span className="font-medium">[{citation.idx}]</span>
                <span className="text-slate-400">
                  {citation.source_file}
                  {citation.page_start && ` p.${citation.page_start}`}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Evidence Cards */}
        {!isUser && message.evidence_cards && message.evidence_cards.length > 0 && (
          <div className="mt-3">
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-300 transition"
            >
              {showEvidence ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
              <span>
                {showEvidence ? 'Hide' : 'Show'} evidence ({message.evidence_cards.length} chunks)
              </span>
            </button>

            {showEvidence && (
              <div className="mt-3 space-y-3">
                {message.evidence_cards.map((card, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-slate-900/50 border border-slate-700/50 rounded-lg"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <span className="font-medium text-blue-400">
                          [{card.citation_idx}]
                        </span>
                        <span>{card.source_file}</span>
                        {card.page_start && <span>• Page {card.page_start}</span>}
                        {card.line_start && <span>• Line {card.line_start}</span>}
                      </div>
                      <div className="text-xs text-slate-500">
                        {(card.similarity * 100).toFixed(1)}% match
                      </div>
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {card.excerpt}
                    </p>
                    {card.why_selected && card.why_selected.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {card.why_selected.map((reason, i) => (
                          <span
                            key={i}
                            className="inline-block px-2 py-0.5 bg-blue-500/10 border border-blue-500/30 rounded text-xs text-blue-300"
                          >
                            {reason}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
