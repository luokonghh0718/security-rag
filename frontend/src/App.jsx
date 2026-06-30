import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'

const API_BASE = '/api'

// ── Axios 拦截器：自动附加 JWT token ──────────────────
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：token 过期自动跳转登录
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      window.location.reload()
    }
    return Promise.reject(error)
  }
)

const QUICK_QUESTIONS = [
  '最近有哪些新漏洞？',
  '什么是SQL注入？',
  'ATT&CK T1059是什么？',
  '如何防御XSS？',
  'Linux内核权限提升漏洞有哪些？',
]

function App({ onLogout }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState({ online: false, chunks: 0 })
  const chatEndRef = useRef(null)

  // 检查服务状态
  useEffect(() => {
    checkStatus()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const checkStatus = async () => {
    try {
      const { data } = await axios.get(API_BASE.replace('/api', '/'))
      setStatus({
        online: data.status === 'running',
        chunks: data.knowledge_loaded ? '已加载' : '未加载',
      })
    } catch {
      setStatus({ online: false, chunks: '离线' })
    }
  }

  const sendMessage = async (text) => {
    const question = text || input.trim()
    if (!question || loading) return

    // 添加用户消息
    const userMsg = { role: 'user', content: question }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    // 添加加载占位
    const loadingId = Date.now()
    setMessages((prev) => [...prev, { role: 'assistant', content: '', loading: true, id: loadingId }])

    try {
      const { data } = await axios.post(`${API_BASE}/query`, { text: question })
      // 替换加载消息
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingId
            ? {
                role: 'assistant',
                content: data.answer,
                sources: data.sources,
                chunks: data.chunks_count,
                loading: false,
              }
            : msg
        )
      )
    } catch (err) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingId
            ? {
                role: 'assistant',
                content: `⚠️ 请求失败: ${err.response?.data?.detail || err.message}`,
                sources: [],
                loading: false,
              }
            : msg
        )
      )
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-primary">
      {/* 顶部导航栏 */}
      <header className="border-b border-border-color bg-card-bg/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent to-blue-500 flex items-center justify-center text-lg">
              🛡️
            </div>
            <div>
              <h1 className="text-base font-semibold text-white">安全知识库 RAG</h1>
              <p className="text-xs text-gray-400">NVD CVE · MITRE ATT&CK</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* 清空对话按钮 */}
            <button
              onClick={() => setMessages([])}
              disabled={messages.length === 0}
              className="px-2.5 py-1 text-xs rounded-lg border border-border-color
                         text-gray-400 hover:text-yellow-400 hover:border-yellow-500/50
                         disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all duration-200 flex items-center gap-1"
              title="清空对话"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
              </svg>
              清空
            </button>

            {/* 退出登录按钮 */}
            <button
              onClick={onLogout}
              className="px-2.5 py-1 text-xs rounded-lg border border-border-color
                         text-gray-400 hover:text-red-400 hover:border-red-500/50
                         transition-all duration-200 flex items-center gap-1"
              title="退出登录"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />
              </svg>
              退出
            </button>

            {/* 在线状态 */}
            <div className="flex items-center gap-2">
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  status.online ? 'bg-green-400 shadow-[0_0_6px_#4ade80]' : 'bg-red-400'
                }`}
              />
              <span className="text-xs text-gray-400">
                {status.online ? `在线 · ${status.chunks}` : '离线'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* 聊天区域 */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-16">
              <div className="text-6xl mb-4">🔍</div>
              <h2 className="text-xl font-semibold text-white mb-2">网络安全智能问答</h2>
              <p className="text-gray-400 mb-8 max-w-md mx-auto">
                基于 NVD CVE 漏洞数据与 MITRE ATT&CK 攻击框架，为您提供专业的安全知识解答
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {QUICK_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="px-3 py-1.5 text-sm rounded-full border border-border-color text-gray-300
                               hover:border-accent hover:text-accent transition-all duration-200
                               bg-card-bg/50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`animate-fade-in ${
                msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'
              }`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-accent/10 border border-accent/30 text-white'
                    : 'bg-card-bg border border-border-color text-gray-200'
                }`}
              >
                {/* 用户头像标识 */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">
                    {msg.role === 'user' ? '👤 你' : '🤖 AI 助手'}
                  </span>
                  {msg.loading && (
                    <span className="text-xs text-accent animate-pulse-slow">思考中...</span>
                  )}
                </div>

                {/* 消息内容 */}
                <div className="markdown-body text-sm">
                  {msg.loading ? (
                    <div className="flex gap-1 py-2">
                      <span className="w-2 h-2 bg-accent rounded-full animate-pulse-slow" />
                      <span className="w-2 h-2 bg-accent rounded-full animate-pulse-slow" style={{ animationDelay: '0.2s' }} />
                      <span className="w-2 h-2 bg-accent rounded-full animate-pulse-slow" style={{ animationDelay: '0.4s' }} />
                    </div>
                  ) : (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  )}
                </div>

                {/* 来源引用 */}
                {msg.sources && msg.sources.length > 0 && !msg.loading && (
                  <div className="mt-3 pt-2 border-t border-border-color/50">
                    <span className="text-xs text-gray-500">📎 参考来源：</span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {msg.sources.map((src, i) => (
                        <span
                          key={i}
                          className={`inline-block px-2 py-0.5 text-xs rounded font-mono ${
                            src.startsWith('CVE')
                              ? 'bg-red-500/10 text-red-400 border border-red-500/30'
                              : src.startsWith('ATT&CK')
                              ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30'
                              : 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                          }`}
                        >
                          {src}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          <div ref={chatEndRef} />
        </div>
      </main>

      {/* 输入区域 */}
      <footer className="border-t border-border-color bg-card-bg/30 backdrop-blur-sm sticky bottom-0">
        <div className="max-w-3xl mx-auto px-4 py-3">
          <div className="flex gap-2 items-end">
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入安全问题，按 Enter 发送..."
                rows={1}
                className="w-full bg-input-bg border border-border-color rounded-xl px-4 py-2.5
                           text-sm text-white placeholder-gray-500 resize-none
                           focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30
                           transition-all duration-200"
                style={{ minHeight: '42px', maxHeight: '120px' }}
                onInput={(e) => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
                }}
              />
            </div>
            <button
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
              className="px-4 py-2.5 rounded-xl bg-accent text-primary font-semibold text-sm
                         hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all duration-200 flex items-center gap-1.5"
            >
              <span>发送</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
          <p className="text-[10px] text-gray-600 text-center mt-2">
            AI 生成内容仅供参考，请结合实际情况判断 · 按 Enter 发送，Shift+Enter 换行
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
