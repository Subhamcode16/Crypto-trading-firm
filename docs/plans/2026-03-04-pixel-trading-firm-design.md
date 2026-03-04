# Design: Pixel Trading Firm (v1)

- **Date**: 2026-03-04
- **Status**: Approved
- **Objective**: Build a real-time pixel-art operations dashboard for a 9-agent autonomous trading system.

## 1. Architecture Overview (Split-Brain)

The project consists of two primary parts:
1.  **Frontend**: React (Vite) + Phaser + Zustand + Tailwind (Hybrid Glassmorphism).
2.  **Mock Server**: A Node.js/WebSocket server to simulate agent behavior and provide a Scenario Controller.

### Event Adapter Layer
To handle future schema changes, a dedicated `EventAdapter` will map raw WebSocket messages to internal application state. This ensures that UI components and Phaser scenes are decoupled from the specific backend data format.

## 2. Visual & Aesthetic

- **Office Canvas**: Top-down pixel art rendered in Phaser. 3 floors + Reception.
- **UI Layers**: React-based overlays using **Hybrid Glassmorphism**.
- **Transparency & Blurs**: Frosted glass effects for desktop panels and mobile sheets.
- **Typography**: Modern, technical sans-serif for status data, pixel fonts for nameplates.

## 3. Key Components

### Phaser Scenes
- `ReceptionScene`: Lobby with vital signs and ticker.
- `Floor1Scene`: Intelligence Division (Agents 1-4).
- `Floor2Scene`: Command Division (Agents 5-7).
- `Floor3Scene`: Execution & Review (Agents 8-9).

### React Dashboard
- **Glassmorphic Panels**: Slide-in details for each agent.
- **Inbox**: Threaded memo system with color-coded signal outcomes.
- **Kill Switch Control**: 4-tier safety panel with manual override confirmation.

## 4. State Management (Zustand)
- `useAgentStore`: Centralized status, presence, and animation triggers.
- `useSignalStore`: Lifecycle tracking of candidates from discovery to trade/kill.
- `useTradeStore`: Live position P&L, entry/exit data, and execution logs.
- `useRiskStore`: Daily loss meters, exposure gauges, and kill-switch states.

## 5. Development Strategy
- **Phase 1**: Project scaffolding and basic Phaser office layout.
- **Phase 2**: AI-generation of pixel art assets (Agents & Tiles).
- **Phase 3**: Integration of Zustand stores and WebSocket Event Adapter.
- **Phase 4**: Implementation of Glassmorphic UI panels and Inbox.
- **Phase 5**: Mock Server and Scenario Controller implementation.

## 6. Success Criteria
- Real-time visual feedback for all 9 agents based on simulated data.
- Fully functional Mobile card-grid view.
- Working Kill Switch system with two-step manual confirmation.
- 100% decoupling between the visual engine and the underlying trade data.
