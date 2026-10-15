import { useEffect, useRef, useState } from 'react'
import './App.css'

const starterPrompts = [
  { icon: 'sparkles', title: 'Explain a tricky concept', prompt: 'Explain the difference between supervised and unsupervised learning.' },
  { icon: 'list', title: 'Turn notes into a summary', prompt: 'Summarize the key ideas from today’s lecture on machine learning.' },
  { icon: 'help', title: 'Quiz me on a topic', prompt: 'Quiz me on the fundamentals of neural networks.' },
  { icon: 'arrows', title: 'Compare two ideas', prompt: 'Compare gradient descent and stochastic gradient descent.' },
]

const initialThreads = [
  { id: 'attention', title: 'Understanding attention layers', messages: [
    { id: 'attention-user', role: 'user', text: 'Why does self-attention help a model understand context?' },
    { id: 'attention-assistant', role: 'assistant', intro: 'Self-attention lets each token look at other tokens and decide which context matters most.', points: ['Each token creates a query, key, and value representation.', 'Similarity between queries and keys determines how much information to gather.', 'The weighted values give each token a context-aware representation.'], source: 'Attention & Transformers · Lecture 08' },
  ] },
  { id: 'probability', title: 'Probability distributions', messages: [
    { id: 'probability-user', role: 'user', text: 'When should I use a normal distribution?' },
    { id: 'probability-assistant', role: 'assistant', intro: 'A normal distribution is a useful model for continuous measurements that cluster around a typical value.', points: ['It is symmetric around its mean.', 'The standard deviation describes how spread out values are.', 'Check the data shape before assuming a normal model is appropriate.'], source: 'Probability & Statistics · Lecture 03' },
  ] },
  { id: 'linear-algebra', title: 'Linear algebra revision', messages: [
    { id: 'linear-algebra-user', role: 'user', text: 'Give me a quick refresher on matrix multiplication.' },
    { id: 'linear-algebra-assistant', role: 'assistant', intro: 'Matrix multiplication combines rows from the first matrix with columns from the second.', points: ['The inner dimensions must match.', 'Each output entry is a dot product of one row and one column.', 'The result has the outer dimensions of the two matrices.'], source: 'Linear Algebra · Lecture 01' },
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
  }

  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function mockReply(prompt) {
  const subject = prompt.replace(/[?.!]+$/, '')

  if (/quiz|test me/i.test(prompt)) {
    return { intro: 'Let’s make this active recall. Answer these without looking anything up:', points: ['What role does an activation function play in a neural network?', 'How do weights and biases affect a neuron’s output?', 'Why can adding more layers help a model learn complex patterns?'], source: 'Neural Networks · Lecture 04' }
  }
  if (/supervised.*unsupervised/i.test(prompt)) {
    return { intro: 'The key difference is whether the training examples come with labels:', points: ['Supervised learning uses labeled examples to learn a mapping from inputs to known answers.', 'Unsupervised learning looks for structure in unlabeled data, such as clusters or compact representations.', 'Use supervised methods when you have target labels; use unsupervised methods to explore patterns without them.'], source: 'Machine Learning Foundations · Lecture 02' }
  }
  if (/^compare\b/i.test(prompt)) {
    return { intro: 'A useful comparison starts with the goal, then looks at how each method reaches it:', points: ['Identify what the two approaches have in common.', 'Compare the information each one uses at each step.', 'That trade-off often explains differences in speed, stability, and results.'], source: 'Optimization Methods · Lecture 06' }
  }
  if (/difference/i.test(prompt)) {
    return { intro: `To understand ${subject.toLowerCase()}, focus on the signal each approach learns from:`, points: ['One approach learns from examples paired with known answers.', 'The other looks for useful structure without those answer labels.', 'That difference determines which problems each approach is best suited to solve.'], source: 'Machine Learning Foundations · Lecture 02' }
  }
  if (/summar|key ideas|notes/i.test(prompt)) {
    return { intro: 'Here’s a concise set of takeaways to study from:', points: ['A model learns by adjusting its parameters to reduce prediction error.', 'Training data provides examples; evaluation data checks whether learning generalizes.', 'The choice of objective and optimization method shapes what the model can learn.'], source: 'Machine Learning Foundations · Lecture 02' }
  }
  return { intro: `Here’s a clear way to think about ${subject.toLowerCase()}:`, points: ['Begin with the basic idea: identify what goes in, what happens, and what comes out.', 'Then connect each step to its purpose rather than memorizing it in isolation.', 'A quick check: explain the concept in one sentence, then give a concrete example.'], source: 'Machine Learning Foundations · Lecture 02' }
}

function App() {
  const [threads, setThreads] = useState(initialThreads)
  const [activeThreadId, setActiveThreadId] = useState('new')
  const [draft, setDraft] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const messagesEndRef = useRef(null)
  const activeThread = threads.find((thread) => thread.id === activeThreadId)
  const messages = activeThread?.messages ?? emptyMessages

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  function startNewChat() {
    setActiveThreadId('new')
    setDraft('')
    setIsThinking(false)
    setSidebarOpen(false)
  }

  function sendMessage(messageText = draft) {
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

    window.setTimeout(() => { //Placeholder for async API call to get assistant response, provideing mock response for now
      const reply = mockReply(text)
      setThreads((currentThreads) => currentThreads.map((thread) => thread.id === threadId
        ? { ...thread, messages: [...thread.messages, { id: `${threadId}-assistant-${messages.length + 1}`, role: 'assistant', ...reply }] }
        : thread))
      setIsThinking(false)
    }, 850)
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
          <button className="nav-button library-link" type="button"><Icon name="book" size={17} /><span>Lecture notes</span></button>
        </div>

        <div className="history-section">
          <div className="history-heading"><span>RECENT</span><button className="icon-button history-more" type="button" aria-label="More recent chat options"><Icon name="more" size={18} /></button></div>
          <div className="thread-list">{threads.filter((thread) => thread.title.toLowerCase().includes(searchQuery.toLowerCase())).map((thread) => (
            <button key={thread.id} className={`thread-button ${thread.id === activeThreadId ? 'thread-active' : ''}`} type="button" onClick={() => { setActiveThreadId(thread.id); setSidebarOpen(false) }}><span className="thread-indicator" /><span className="thread-title">{thread.title}</span><span className="thread-menu"><Icon name="more" size={16} /></span></button>
          ))}</div>
        </div>

        <div className="sidebar-bottom">
          <div className="plan-note"><span className="plan-icon"><Icon name="sparkles" size={16} /></span><div><strong>Your study space</strong><span>Ready when you are</span></div><Icon name="more" size={17} /></div>
          <button className="profile-button" type="button"><span className="avatar">T</span><span className="profile-copy"><strong>Tejas</strong><small>Free plan</small></span><Icon name="more" size={17} /></button>
        </div>
      </aside>

      {sidebarOpen && <button className="sidebar-scrim" type="button" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}

      <section className="chat-panel">
        <header className="topbar">
          <div className="topbar-left"><button className="icon-button mobile-menu" type="button" aria-label="Open sidebar" onClick={() => setSidebarOpen(true)}><Icon name="menu" /></button><div className="course-label"><span className="course-dot" /><span>STUDY ASSISTANT</span></div></div>
          <div className="topbar-right"><label className="model-picker"><span className="model-status" /><select aria-label="Choose assistant model" defaultValue="Study partner"><option>Study partner</option><option>Quick answers</option><option>Deep focus</option></select></label><button className="share-button" type="button" onClick={() => navigator.clipboard?.writeText(window.location.href)}>Share</button></div>
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
              <div className="source-hint"><span className="source-hint-icon"><Icon name="book" size={16} /></span><span>Ground answers in your course material, or just ask anything.</span></div>
            </div>
          ) : (
            <div className="message-list" aria-live="polite">
              {messages.map((message) => (
                <article className={`message message-${message.role}`} key={message.id}>
                  {message.role === 'assistant' ? <span className="assistant-mark"><Icon name="sparkles" size={17} /></span> : <span className="user-mark">T</span>}
                  <div className="message-body"><div className="message-author">{message.role === 'assistant' ? 'Study partner' : 'You'}</div>
                    {message.role === 'user' ? <p>{message.text}</p> : <><p>{message.intro}</p><ul>{message.points.map((point) => <li key={point}>{point}</li>)}</ul><button className="source-chip" type="button"><Icon name="book" size={14} /> {message.source}<span>↗</span></button></>}
                  </div>
                </article>
              ))}
              {isThinking && <div className="thinking-row"><span className="assistant-mark"><Icon name="sparkles" size={17} /></span><div><div className="message-author">Study partner</div><span className="thinking-dots"><i /><i /><i /></span></div></div>}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="composer-area"><div className="composer">
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder="Ask anything about your studies..." rows="1" aria-label="Message study partner" />
          <div className="composer-controls"><button className="attach-button" type="button" aria-label="Attach a file" title="Attach a file"><Icon name="paperclip" size={18} /></button><div className="composer-right"><span className="enter-hint">Press <kbd>↵</kbd> to send</span><button className="send-button" type="button" aria-label="Send message" disabled={!draft.trim() || isThinking} onClick={() => sendMessage()}><Icon name="send" size={17} /></button></div></div>
        </div><p className="disclaimer">Leccript can make mistakes. Check important information against your course materials.</p></div>
      </section>
    </main>
  )
}

export default App
