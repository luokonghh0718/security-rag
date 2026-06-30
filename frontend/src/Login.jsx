import React, { useState } from 'react'
import axios from 'axios'

const API_BASE = '/api'

function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) {
      setError('请输入用户名和密码')
      return
    }

    setLoading(true)
    setError('')

    try {
      const { data } = await axios.post(`${API_BASE}/auth/login`, {
        username: username.trim(),
        password: password,
      })

      if (data.success) {
        localStorage.setItem('auth_token', data.token)
        onLoginSuccess()
      } else {
        setError(data.message || '登录失败')
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError('用户名或密码错误')
      } else {
        setError(err.response?.data?.detail || '登录服务不可用，请稍后重试')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleLogin(e)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-primary">
      <div className="w-full max-w-sm px-6">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-accent to-blue-500 flex items-center justify-center text-3xl">
            🛡️
          </div>
          <h1 className="text-xl font-semibold text-white">安全知识库 RAG</h1>
          <p className="text-sm text-gray-400 mt-1">NVD CVE · MITRE ATT&CK</p>
        </div>

        {/* 登录表单 */}
        <form onSubmit={handleLogin} className="bg-card-bg border border-border-color rounded-2xl p-6 space-y-4">
          <h2 className="text-sm font-medium text-gray-300 text-center">🔐 登录认证</h2>

          {/* 错误提示 */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-xs text-red-400">
              {error}
            </div>
          )}

          {/* 用户名 */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="请输入用户名"
              autoFocus
              className="w-full bg-input-bg border border-border-color rounded-lg px-3 py-2.5
                         text-sm text-white placeholder-gray-500
                         focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30
                         transition-all duration-200"
            />
          </div>

          {/* 密码 */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="请输入密码"
              className="w-full bg-input-bg border border-border-color rounded-lg px-3 py-2.5
                         text-sm text-white placeholder-gray-500
                         focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30
                         transition-all duration-200"
            />
          </div>

          {/* 登录按钮 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-accent text-primary font-semibold text-sm
                       hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                登录中...
              </>
            ) : (
              '登 录'
            )}
          </button>

          {/* 提示 */}
          <p className="text-[10px] text-gray-600 text-center">
            默认账号: hwj / 2004
          </p>
        </form>
      </div>
    </div>
  )
}

export default Login
