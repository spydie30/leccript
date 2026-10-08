# Frontend Development

The active frontend is a React 19 single-page app built with Vite. The `use-chat-example/` directory is a separate Create React App example; it is not imported by the active app.

## Run It

From `frontend/leccript-frontend`:

```sh
npm install
npm run dev
npm run lint
npm run build
npm run preview
```

`npm run dev` starts the local Vite server. `npm run build` creates production assets in `dist/`, and `npm run preview` serves that build locally.

## App Structure

- `index.html` provides the root element, browser title, and theme color.
- `src/main.jsx` imports global CSS and mounts `<App />` inside React `StrictMode`.
- `src/App.jsx` contains the chat UI, sample conversations, local interaction state, and mock reply handler.
- `src/index.css` defines global resets, typography, and app-wide color variables.
- `src/App.css` styles the chat workspace, messages, composer, sidebar, and responsive layouts.
- `vite.config.js` enables the React plugin; `package.json` defines scripts and dependencies.

## Chat Flow

`App` owns the in-memory chat state:

- `threads` stores conversation titles and messages. Three sample conversations seed the history.
- `activeThreadId` selects the visible conversation. The value `new` represents the welcome screen before a first message is sent.
- `draft` controls the composer text, and `isThinking` disables duplicate sends while the mock reply is pending.
- `sidebarOpen` controls mobile navigation; `searchOpen` and `searchQuery` control filtering in the history list.

Starter cards and the composer both call `sendMessage`. It appends a user message, creates a thread when needed, waits briefly, then appends the result from `mockReply`. Press Enter to send; Shift+Enter keeps a line break. A ref and effect scroll the conversation to the newest content.

`mockReply` is the API boundary for this prototype. It returns an `intro`, a list of `points`, and a `source` label based on simple prompt matching. Replace this function and the timeout in `sendMessage` with an async API call when the backend is ready. Keep the rendered assistant message shape, or update the message renderer to match the backend response. Current conversations are in memory only and reset on page reload; displayed source labels are sample data, not retrieved citations.

The search field filters thread titles, and Share copies the current page URL when clipboard access is available. Model selection, Lecture notes, attachment, profile, and overflow controls are visual placeholders and do not yet invoke application services.

## Styling Notes

Use `index.css` for global defaults and variables such as `--canvas` and `--sidebar`. Use `App.css` for component and responsive rules. Mobile navigation switches to a slide-out sidebar below 680px; the compact header and prompt cards adjust again below 380px.