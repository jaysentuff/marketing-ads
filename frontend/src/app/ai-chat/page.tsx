'use client';

import { useEffect, useState, useRef } from 'react';
import { api, type ChatMessage, type ChatSession } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import {
  Send,
  Bot,
  User,
  Loader2,
  AlertCircle,
  Sparkles,
  Plus,
  MessageSquare,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export default function AIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiStatus, setAiStatus] = useState<{ available: boolean; api_key_set: boolean } | null>(null);
  const [quickQuestions, setQuickQuestions] = useState<Array<{ id: string; label: string; question: string }>>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const init = async () => {
      try {
        const [status, questions, sessionsData] = await Promise.all([
          api.getAiStatus(),
          api.getQuickQuestions(),
          api.getChatSessions(),
        ]);
        setAiStatus(status);
        setQuickQuestions(questions.questions);
        setSessions(sessionsData.sessions);

        // Load most recent session if exists
        if (sessionsData.sessions.length > 0) {
          const latestSession = sessionsData.sessions[0];
          const fullSession = await api.getChatSession(latestSession.id);
          setCurrentSessionId(latestSession.id);
          setMessages(fullSession.session.messages || []);
        }
      } catch (err) {
        console.error('Failed to init AI chat:', err);
      }
    };
    init();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const saveMessages = async (newMessages: ChatMessage[], sessionId: string | null) => {
    try {
      if (sessionId) {
        await api.updateChatSession(sessionId, newMessages);
        // Refresh sessions list
        const sessionsData = await api.getChatSessions();
        setSessions(sessionsData.sessions);
      }
    } catch (err) {
      console.error('Failed to save messages:', err);
    }
  };

  const sendMessage = async (content: string) => {
    if (!content.trim() || loading) return;

    let sessionId = currentSessionId;

    // Create new session if none exists
    if (!sessionId) {
      try {
        const { session } = await api.createChatSession();
        sessionId = session.id;
        setCurrentSessionId(sessionId);
        setSessions((prev) => [session, ...prev]);
      } catch (err) {
        console.error('Failed to create session:', err);
        return;
      }
    }

    const userMessage: ChatMessage = { role: 'user', content };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const response = await api.chat(newMessages);
      const assistantMessage: ChatMessage = { role: 'assistant', content: response.message };
      const updatedMessages = [...newMessages, assistantMessage];
      setMessages(updatedMessages);
      await saveMessages(updatedMessages, sessionId);
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
      };
      const updatedMessages = [...newMessages, errorMessage];
      setMessages(updatedMessages);
      await saveMessages(updatedMessages, sessionId);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleQuickQuestion = (question: string) => {
    sendMessage(question);
  };

  const startNewChat = async () => {
    try {
      const { session } = await api.createChatSession();
      setCurrentSessionId(session.id);
      setMessages([]);
      setSessions((prev) => [session, ...prev]);
    } catch (err) {
      console.error('Failed to create new chat:', err);
    }
  };

  const loadSession = async (sessionId: string) => {
    try {
      const { session } = await api.getChatSession(sessionId);
      setCurrentSessionId(session.id);
      setMessages(session.messages || []);
    } catch (err) {
      console.error('Failed to load session:', err);
    }
  };

  const deleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteChatSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  if (aiStatus && !aiStatus.available) {
    return (
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">AI Assistant</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-8 text-center">
          <AlertCircle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-yellow-800">AI Not Available</h2>
          <p className="text-yellow-700 mt-2">
            {!aiStatus.api_key_set
              ? 'Please set ANTHROPIC_API_KEY in your .env file'
              : 'Anthropic library not installed. Run: pip install anthropic'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)]">
      {/* Chat History Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-64' : 'w-0'
        } transition-all duration-300 overflow-hidden border-r border-gray-200 bg-gray-50 flex flex-col`}
      >
        <div className="p-4 border-b border-gray-200">
          <button
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Plus size={18} />
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sessions.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No chat history yet</p>
          ) : (
            <div className="space-y-1">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => loadSession(session.id)}
                  className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                    currentSessionId === session.id
                      ? 'bg-primary-100 text-primary-700'
                      : 'hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  <MessageSquare size={16} className="flex-shrink-0" />
                  <span className="flex-1 text-sm truncate">{session.title}</span>
                  <button
                    onClick={(e) => deleteSession(session.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 rounded transition-opacity"
                  >
                    <Trash2 size={14} className="text-gray-500" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Toggle Sidebar Button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute left-0 top-1/2 -translate-y-1/2 z-10 bg-white border border-gray-200 rounded-r-lg p-1 hover:bg-gray-50"
        style={{ left: sidebarOpen ? '256px' : '0' }}
      >
        {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
      </button>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col max-w-4xl mx-auto px-4">
        <div className="mb-6 pt-4">
          <h1 className="text-3xl font-bold text-gray-900">AI Marketing Assistant</h1>
          <p className="text-gray-500 mt-1">
            Ask questions about your marketing performance and get AI-powered insights
          </p>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-auto bg-white rounded-xl border border-gray-200 p-4 mb-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <Sparkles className="h-12 w-12 text-primary-500 mb-4" />
              <h2 className="text-xl font-semibold text-gray-900">Start a Conversation</h2>
              <p className="text-gray-500 mt-2 max-w-md">
                Ask about your marketing performance, CMAM metrics, TOF campaigns, or get recommendations
                for budget optimization.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
                      <Bot className="h-5 w-5 text-primary-600" />
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    {msg.role === 'assistant' ? (
                      <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:text-gray-700 prose-li:text-gray-700">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                      <User className="h-5 w-5 text-gray-600" />
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                    <Bot className="h-5 w-5 text-primary-600" />
                  </div>
                  <div className="bg-gray-100 rounded-xl px-4 py-3">
                    <Loader2 className="h-5 w-5 animate-spin text-gray-500" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Quick Questions */}
        {messages.length === 0 && quickQuestions.length > 0 && (
          <div className="mb-4">
            <p className="text-sm text-gray-500 mb-2">Quick questions:</p>
            <div className="flex flex-wrap gap-2">
              {quickQuestions.map((q) => (
                <button
                  key={q.id}
                  onClick={() => handleQuickQuestion(q.question)}
                  className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="flex gap-3 pb-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your marketing performance..."
            className="flex-1 px-4 py-3 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-gray-900 placeholder-gray-400"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-6 py-3 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <Send className="h-5 w-5" />
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
