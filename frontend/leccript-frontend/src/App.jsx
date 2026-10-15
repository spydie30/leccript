import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

const starterPrompts = [
  { icon: 'sparkles', title: 'Explain a tricky concept', prompt: 'Explain the difference between supervised and unsupervised learning.' },
  { icon: 'list', title: 'Turn notes into a summary', prompt: 'Summarize the key ideas from the lecture.' },
  { icon: 'help', title: 'What did the professor say?', prompt: 'What did the professor say about the N3 segmentation problem?' },
  { icon: 'arrows', title: 'Compare two ideas', prompt: 'Compare gradient descent and stochastic gradient descent.' },
]

const initialThreads = [
  { id: 'attention', title: 'Understanding attention layers', messages: [
    { id: 'attention-user', role: 'user', text: 'Why does self-attention help a model understand context?' },
    { id: 'attention-assistant', role: 'assistant', intro: 'Self-attention lets each token look at other tokens and decide which context matters most.', points: ['Each token creates a query, key, and value representation.', 'Similarity between queries and keys determines how much information to gather.', 'The weighted values give each token a context-aware representation.'], source: 'Attention & Transformers · Lecture 08', citations: [] },
  ] },
]
const emptyMessages = []

function Icon({ name, size = 18 }) {
  const paths = {
    plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    sparkles: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-2-5.8L4 11l6-2.2L12 3Z" /><path d="m19 14 .9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14Z" /></>,
    list: <><path d="M9 6h11" /><path d="M9 12h11" /><path d="M9 18h11" /><path d="M4 6h.01" /><path d="M4 12h.01" /><path d="M4 18h.01" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.6 9a2.5 2.5 0 1 1 4.2 1.8c-1.2 1-1.8 1.4-1.8 2.7" /><path d="M12 17h.01" /></>,
    arrows: <><path d="M7 7h13l-3-3" /><path d="m20 7-3 3" /><path d="M17 17H4l3 3" /><path d="m4 17 3-3" /></>,
    paperclip: <><path d="m21.4 11.1-8.5 8.5a5 5 0 0 1-7.1-7.1l9.2-9.2a3.5 3.5 0 0 1 5 5l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    menu: <><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /></>,
    more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5z" /><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20" /><path d="M8 7h8" /></>,
    close: <><path d="M18 6 6 18" /><path d="m6 6 12 12" /></>,
    trash: <><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /></>,
  }

  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function parseFilenameHint(filename) {
  const match = filename.match(/^(.+?)-(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{8})-([^.]+)\.(?:txt|vtt|srt)$/i)
  if (!match) return { professor: '', lectureDate: '', courseCode: '' }
  const prof = match[1].replace(/[_\s]+/g, ' ').trim()
  let dateStr = match[2]
  if (/^\d{2}-\d{2}-\d{4}$/.test(dateStr)) {
    const [d, m, y] = dateStr.split('-')
    dateStr = `${y}-${m}-${d}`
  } else if (/^\d{8}$/.test(dateStr)) {
    dateStr = `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
  }
  return { professor: prof, lectureDate: dateStr, courseCode: match[3].toUpperCase() }
}

function App() {
  const [threads, setThreads] = useState(initialThreads)
  const [activeThreadId, setActiveThreadId] = useState('new')
  const [draft, setDraft] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Backend state
  const [lectures, setLectures] = useState([])
  const [selectedCourse, setSelectedCourse] = useState('')
  const [studyMode, setStudyMode] = useState('Study partner')
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [activeCitation, setActiveCitation] = useState(null)

  // Upload form state
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadProf, setUploadProf] = useState('')
  const [uploadCourse, setUploadCourse] = useState('')
  const [uploadDate, setUploadDate] = useState('')
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadRecordingUrl, setUploadRecordingUrl] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)

  const messagesEndRef = useRef(null)
  const quickFileInputRef = useRef(null)
  const activeThread = threads.find((thread) => thread.id === activeThreadId)
  const messages = activeThread?.messages ?? emptyMessages

  const courses = Array.from(new Set(lectures.map((l) => l.course_code))).sort()

  async function fetchLectures() {
    try {
      const resp = await fetch(`${API_BASE}/api/lectures`)
      if (resp.ok) {
        const data = await resp.json()
        setLectures(data)
      }
    } catch {
      // Backend offline or starting up
    }
  }

  useEffect(() => {
    fetchLectures()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  function startNewChat() {
    setActiveThreadId('new')
    setDraft('')
    setIsThinking(false)
    setSidebarOpen(false)
  }

  function handleSelectFile(file) {
    if (!file) return
    setUploadFile(file)
    const hints = parseFilenameHint(file.name)
    if (hints.professor) setUploadProf(hints.professor)
    if (hints.courseCode) setUploadCourse(hints.courseCode)
    if (hints.lectureDate) setUploadDate(hints.lectureDate)
    setUploadStatus(null)
    setLibraryOpen(true)
  }

  async function handleIngestSubmit(event) {
    event.preventDefault()
    if (!uploadFile || isUploading) return

    setIsUploading(true)
    setUploadStatus(null)
    const formData = new FormData()
    formData.append('file', uploadFile)
    if (uploadProf.trim()) formData.append('professor', uploadProf.trim())
    if (uploadCourse.trim()) formData.append('course_code', uploadCourse.trim())
    if (uploadDate.trim()) formData.append('lecture_date', uploadDate.trim())
    if (uploadTitle.trim()) formData.append('title', uploadTitle.trim())
    if (uploadRecordingUrl.trim()) formData.append('recording_url', uploadRecordingUrl.trim())

    try {
      const resp = await fetch(`${API_BASE}/api/lectures/ingest`, {
        method: 'POST',
        body: formData,
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.detail || 'Upload failed')
      }
      setUploadStatus({
        type: 'success',
        text: `${data.already_existed ? 'Already indexed' : 'Ingested'} ${data.course_code} · Prof. ${data.professor} (${data.cues_count} cues, ${data.chunks_count} chunks)`,
      })
      setUploadFile(null)
      setUploadTitle('')
      setUploadRecordingUrl('')
      await fetchLectures()
    } catch (err) {
      setUploadStatus({ type: 'error', text: err.message })
    } finally {
      setIsUploading(false)
    }
  }

  async function handleDeleteLecture(lectureId) {
    try {
      const resp = await fetch(`${API_BASE}/api/lectures/${lectureId}`, { method: 'DELETE' })
      if (resp.ok) {
        await fetchLectures()
      }
    } catch {
      // Ignore error
    }
  }

  async function sendMessage(messageText = draft) {
    const text = messageText.trim()
    if (!text || isThinking) return

    const threadId = activeThreadId === 'new' ? `chat-${threads.length + 1}` : activeThreadId
    const userMessage = { id: `${threadId}-user-${messages.length}`, role: 'user', text }

    setThreads((currentThreads) => {
      const existingThread = currentThreads.find((thread) => thread.id === threadId)
      if (existingThread) {
        return currentThreads.map((thread) => thread.id === threadId ? { ...thread, messages: [...thread.messages, userMessage] } : thread)
      }
      return [{ id: threadId, title: text.slice(0, 34), messages: [userMessage] }, ...currentThreads]
    })
    setActiveThreadId(threadId)
    setDraft('')
    setIsThinking(true)

    try {
      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: text,
          course_code: selectedCourse || null,
          lecturer_only: studyMode === 'Professor only',
          top_k: studyMode === 'Deep focus' ? 6 : 4,
        }),
      })

      if (!resp.ok) {
        throw new Error(`Server error (${resp.status})`)
      }
      const reply = await resp.json()
      setThreads((currentThreads) => currentThreads.map((thread) => thread.id === threadId
        ? {
            ...thread,
            messages: [
              ...thread.messages,
              {
                id: `${threadId}-assistant-${ Date.now() }`,
                role: 'assistant',
                intro: reply.intro,
                points: reply.points || [],
                source: reply.source || 'Lecture Library',
                citations: reply.citations || [],
              },
            ],
          }
        : thread))
    } catch (err) {
      setThreads((currentThreads) => currentThreads.map((thread) => thread.id === threadId
        ? {
            ...thread,
            messages: [
              ...thread.messages,
              {
                id: `${threadId}-assistant-${ Date.now() }`,
                role: 'assistant',
                intro: 'Could not reach the Lecture RAG backend.',
                points: [
                  `Details: ${err.message}`,
                  'Make sure the FastAPI server is running on port 8000 (`docker compose up --build`).',
                ],
                source: 'Connection Error',
                citations: [],
              },
            ],
          }
        : thread))
    } finally {
      setIsThinking(false)
    }
  }

  function handleComposerKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }

  return (
    <main className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-row">
          <a className="brand" href="#home" onClick={startNewChat} aria-label="Leccript home"><span className="brand-mark"><Icon name="book" size={20} /></span><span>leccript</span></a>
          <button className="icon-button sidebar-close" type="button" aria-label="Close sidebar" onClick={() => setSidebarOpen(false)}><Icon name="menu" /></button>
        </div>

        <button className="new-chat-button" type="button" onClick={startNewChat}><Icon name="plus" size={17} /><span>New study chat</span><span className="shortcut">⌘ K</span></button>

        <div className="sidebar-tools">
          <button className="nav-button" type="button" onClick={() => setSearchOpen((open) => !open)}><Icon name="search" size={17} /><span>Search chats</span><span className="shortcut">⌘ /</span></button>
          {searchOpen && <input className="search-input" autoFocus placeholder="Search your chats" aria-label="Search chats" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} />}
          <div className="section-label">YOUR LIBRARY</div>
          <button className="nav-button library-link" type="button" onClick={() => setLibraryOpen(true)}>
            <Icon name="book" size={17} />
            <span>Lecture notes</span>
            <span className="shortcut">{lectures.length}</span>
          </button>
        </div>

        <div className="history-section">
          <div className="history-heading"><span>RECENT</span><button className="icon-button history-more" type="button" aria-label="More recent chat options"><Icon name="more" size={18} /></button></div>
          <div className="thread-list">{threads.filter((thread) => thread.title.toLowerCase().includes(searchQuery.toLowerCase())).map((thread) => (
            <button key={thread.id} className={`thread-button ${thread.id === activeThreadId ? 'thread-active' : ''}`} type="button" onClick={() => { setActiveThreadId(thread.id); setSidebarOpen(false) }}><span className="thread-indicator" /><span className="thread-title">{thread.title}</span><span className="thread-menu"><Icon name="more" size={16} /></span></button>
          ))}</div>
        </div>

        <div className="sidebar-bottom">
          <div className="plan-note"><span className="plan-icon"><Icon name="sparkles" size={16} /></span><div><strong>{lectures.length} lectures indexed</strong><span>Hybrid RRF + Verbatim cues</span></div><Icon name="more" size={17} /></div>
          <button className="profile-button" type="button"><span className="avatar">T</span><span className="profile-copy"><strong>Tejas</strong><small>Free plan</small></span><Icon name="more" size={17} /></button>
        </div>
      </aside>

      {sidebarOpen && <button className="sidebar-scrim" type="button" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}

      <section className="chat-panel">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" type="button" aria-label="Open sidebar" onClick={() => setSidebarOpen(true)}><Icon name="menu" /></button>
            <div className="course-label">
              <span className="course-dot" />
              <span>{selectedCourse ? `COURSE: ${selectedCourse}` : 'STUDY ASSISTANT'}</span>
            </div>
          </div>
          <div className="topbar-right">
            <label className="model-picker">
              <select
                aria-label="Filter by course"
                value={selectedCourse}
                onChange={(e) => setSelectedCourse(e.target.value)}
              >
                <option value="">All courses ({lectures.length})</option>
                {courses.map((code) => (
                  <option key={code} value={code}>{code}</option>
                ))}
              </select>
            </label>
            <label className="model-picker">
              <span className="model-status" />
              <select
                aria-label="Choose assistant mode"
                value={studyMode}
                onChange={(e) => setStudyMode(e.target.value)}
              >
                <option value="Study partner">Study partner</option>
                <option value="Professor only">Professor only</option>
                <option value="Deep focus">Deep focus</option>
              </select>
            </label>
            <button className="share-button" type="button" onClick={() => setLibraryOpen(true)}>+ Upload</button>
          </div>
        </header>

        <div className={`conversation ${messages.length === 0 ? 'conversation-empty' : ''}`}>
          {messages.length === 0 ? (
            <div className="welcome-content">
              <div className="welcome-eyebrow"><span className="eyebrow-line" /> YOUR PERSONAL STUDY SPACE <span className="eyebrow-line" /></div>
              <h1>Good to see you,<br /><span>Tejas.</span></h1>
              <p className="welcome-subtitle">What are we learning today?</p>
              <div className="prompt-grid">{starterPrompts.map((item) => (
                <button className="prompt-card" key={item.title} type="button" onClick={() => sendMessage(item.prompt)}><span className={`prompt-icon prompt-icon-${item.icon}`}><Icon name={item.icon} size={18} /></span><span className="prompt-title">{item.title}</span><span className="prompt-arrow">↗</span></button>
              ))}</div>
              <div className="source-hint"><span className="source-hint-icon"><Icon name="book" size={16} /></span><span>Ground answers in your course material ({lectures.length} lectures indexed), or upload a transcript.</span></div>
            </div>
          ) : (
            <div className="message-list" aria-live="polite">
              {messages.map((message) => (
                <article className={`message message-${message.role}`} key={message.id}>
                  {message.role === 'assistant' ? <span className="assistant-mark"><Icon name="sparkles" size={17} /></span> : <span className="user-mark">T</span>}
                  <div className="message-body"><div className="message-author">{message.role === 'assistant' ? 'Study partner' : 'You'}</div>
                    {message.role === 'user' ? (
                      <p>{message.text}</p>
                    ) : (
                      <>
                        <p>{message.intro}</p>
                        {message.points?.length > 0 && (
                          <ul>{message.points.map((point, idx) => <li key={`${message.id}-pt-${idx}`}>{point}</li>)}</ul>
                        )}
                        <div className="citation-list">
                          {message.citations && message.citations.length > 0 ? (
                            message.citations.map((cit) => (
                              <button
                                key={cit.chunk_id}
                                className="source-chip"
                                type="button"
                                onClick={() => setActiveCitation(cit)}
                              >
                                <Icon name="book" size={14} />
                                <span>[{cit.chunk_id}] {cit.label}</span>
                                <span>↗</span>
                              </button>
                            ))
                          ) : (
                            <button className="source-chip" type="button">
                              <Icon name="book" size={14} /> {message.source}<span>↗</span>
                            </button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </article>
              ))}
              {isThinking && <div className="thinking-row"><span className="assistant-mark"><Icon name="sparkles" size={17} /></span><div><div className="message-author">Study partner</div><span className="thinking-dots"><i /><i /><i /></span></div></div>}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="composer-area">
          <div className="composer">
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder="Ask anything about your lectures (e.g., What did Prof. Khare say about N3?)..." rows="1" aria-label="Message study partner" />
            <div className="composer-controls">
              <input
                ref={quickFileInputRef}
                type="file"
                accept=".txt,.vtt,.srt"
                style={{ display: 'none' }}
                onChange={(e) => handleSelectFile(e.target.files?.[0])}
              />
              <button
                className="attach-button"
                type="button"
                aria-label="Upload lecture transcript"
                title="Upload lecture transcript (.txt, .vtt, .srt)"
                onClick={() => quickFileInputRef.current?.click()}
              >
                <Icon name="paperclip" size={18} />
              </button>
              <div className="composer-right">
                <span className="enter-hint">Press <kbd>↵</kbd> to send</span>
                <button className="send-button" type="button" aria-label="Send message" disabled={!draft.trim() || isThinking} onClick={() => sendMessage()}><Icon name="send" size={17} /></button>
              </div>
            </div>
          </div>
          <p className="disclaimer">Citations and timestamps are verified directly against lecture cues in PostgreSQL.</p>
        </div>
      </section>

      {/* Lecture Notes Library & Transcript Ingestion Modal */}
      {libraryOpen && (
        <div className="modal-backdrop" onClick={() => setLibraryOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Lecture Notes Library</h2>
                <p>Upload Zoom, WebVTT, or SRT transcripts with speaker and timestamp indexing.</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setLibraryOpen(false)} aria-label="Close modal">
                <Icon name="close" size={18} />
              </button>
            </div>

            <form className="ingest-form" onSubmit={handleIngestSubmit}>
              <div className="form-row">
                <label className="file-drop-label">
                  <input
                    type="file"
                    accept=".txt,.vtt,.srt"
                    onChange={(e) => handleSelectFile(e.target.files?.[0])}
                  />
                  <span>{uploadFile ? `Selected: ${uploadFile.name}` : 'Choose transcript (.txt, .vtt, .srt) — e.g. prof_name-2026-09-14-DS101.txt'}</span>
                </label>
              </div>
              <div className="form-grid">
                <input
                  type="text"
                  placeholder="Professor (auto from filename)"
                  value={uploadProf}
                  onChange={(e) => setUploadProf(e.target.value)}
                />
                <input
                  type="text"
                  placeholder="Course Code (e.g. DS101)"
                  value={uploadCourse}
                  onChange={(e) => setUploadCourse(e.target.value)}
                />
                <input
                  type="date"
                  value={uploadDate}
                  onChange={(e) => setUploadDate(e.target.value)}
                />
              </div>
              <div className="form-grid-2">
                <input
                  type="text"
                  placeholder="Lecture title (optional)"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                />
                <input
                  type="url"
                  placeholder="Recording URL for timestamp jump (optional)"
                  value={uploadRecordingUrl}
                  onChange={(e) => setUploadRecordingUrl(e.target.value)}
                />
              </div>
              <div className="form-actions">
                <button className="primary-btn" type="submit" disabled={!uploadFile || isUploading}>
                  {isUploading ? 'Ingesting & Embedding...' : 'Ingest Transcript'}
                </button>
                {uploadStatus && (
                  <span className={`status-badge status-${uploadStatus.type}`}>{uploadStatus.text}</span>
                )}
              </div>
            </form>

            <div className="lecture-table-wrap">
              <h3>Indexed Lectures ({lectures.length})</h3>
              {lectures.length === 0 ? (
                <p className="empty-note">No lectures ingested yet. Upload a transcript above to get started.</p>
              ) : (
                <div className="lecture-items">
                  {lectures.map((lec) => (
                    <div className="lecture-item" key={lec.id}>
                      <div>
                        <strong>{lec.course_code} · {lec.title || lec.source_filename}</strong>
                        <small>
                          Prof. {lec.professor} (Speaker label: {lec.lecturer_speaker || 'Auto'}) · {lec.lecture_date} · {lec.cues_count} cues / {lec.chunks_count} chunks
                        </small>
                      </div>
                      <div className="lecture-item-actions">
                        <button
                          className="share-button"
                          type="button"
                          onClick={() => {
                            setSelectedCourse(lec.course_code)
                            setLibraryOpen(false)
                          }}
                        >
                          Filter Chat
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          title="Delete lecture"
                          onClick={() => handleDeleteLecture(lec.id)}
                        >
                          <Icon name="trash" size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Verbatim Citation & Timestamp Inspector Modal */}
      {activeCitation && (
        <div className="modal-backdrop" onClick={() => setActiveCitation(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Source [{activeCitation.chunk_id}] · {activeCitation.course_code}</h2>
                <p>
                  Prof. {activeCitation.professor} · {activeCitation.lecture_date} · Timestamp {activeCitation.timestamp_start} – {activeCitation.timestamp_end} (Lecturer share: {Math.round(activeCitation.lecturer_share * 100)}%)
                </p>
              </div>
              <button className="icon-button" type="button" onClick={() => setActiveCitation(null)} aria-label="Close citation">
                <Icon name="close" size={18} />
              </button>
            </div>

            {activeCitation.jump_url && (
              <div className="jump-banner">
                <a href={activeCitation.jump_url} target="_blank" rel="noreferrer" className="primary-btn">
                  Jump to Recording @ {activeCitation.timestamp_start} ({Math.floor(activeCitation.start_s)}s) ↗
                </a>
              </div>
            )}

            <div className="cue-list">
              {activeCitation.cues?.map((cue) => (
                <div key={cue.idx} className={`cue-row ${cue.is_lecturer ? 'cue-lecturer' : 'cue-student'}`}>
                  <span className="cue-ts">{cue.timestamp}</span>
                  <div className="cue-content">
                    <strong>
                      {cue.speaker || 'Speaker'}
                      {cue.is_lecturer ? <span className="role-pill">Lecturer</span> : <span className="role-pill role-student">Student</span>}
                    </strong>
                    <p>{cue.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

export default App