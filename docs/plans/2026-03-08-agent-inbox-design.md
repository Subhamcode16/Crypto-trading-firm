# Design: Agent Inbox (Message Pipeline)

## Overview
The Agent Inbox is a transparency-focused communication layer for the trading office. It allows users to monitor the "hidden" dialogue between agents in real-time, visualizing how data flows from discovery to execution.

## Proposed Changes

### Core Logic: Message Tracking
- **[NEW] [useMessageStore.js](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/frontend/src/stores/useMessageStore.js)**:
  - Stores an array of `messages`.
  - Each message contains: `id`, `timestamp`, `senderId`, `receiverId`, `content`, `type` (e.g., signal, risk, trade).
  - Methods: `addMessage(msg)`, `clearMessages()`.

### UI Components
- **[NEW] [InboxDrawer.jsx](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/frontend/src/components/panels/InboxDrawer.jsx)**:
  - A slide-over right panel using `framer-motion`.
  - Features a "Glassmorphism" aesthetic (`bg-[#050505]/80 backdrop-blur-xl`).
  - Left sidebar within the drawer to select an agent (Threaded View).
  - Main area showing the message stream for the selected agent.
- **[MODIFY] [Header.jsx](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/frontend/src/components/layout/Header.jsx)**:
  - Add an "Inbox" toggle button with a notification badge.

### Integration
- **[MODIFY] [EventAdapter.js](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/frontend/src/logic/EventAdapter.js)**:
  - Update `routeEvent` to push messages to `useMessageStore`.
  - For example, when `SIGNAL_FOUND` in Researcher, it also logs: "Researcher -> SignalAggregator: Found potential BTC long setup (89% confidence)".

## UI/UX Design (Premium Command Center)
- **Style**: Dark mode, frosted glass, border-glow on active threads.
- **Interaction**:
  - Slide-in from right.
  - Smooth staggering of new messages.
  - Hovering a message highlights the corresponding agent in the background (optional).

## Verification Plan
### Automated Tests
- `npm run test` (if applicable) for the store logic.
- `npm run build` to ensure no breaks.
### Manual Verification
- Open Dev Menu.
- Trigger "SIGNAL_FOUND".
- Open Inbox and verify the message appears under "Researcher" or "Global Pipeline".
