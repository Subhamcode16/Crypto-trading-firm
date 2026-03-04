// Central mutable state for the pure canvas engine (avoids putting high-frequency game logic into React Zustand)

export const CharacterState = {
    IDLE: 'IDLE',
    WALK: 'WALK',
    WORKING: 'WORKING',
    SIGNAL_FOUND: 'SIGNAL_FOUND',
    VERIFYING: 'VERIFYING',
    STAMPING_GREEN: 'STAMPING_GREEN',
    STAMPING_RED: 'STAMPING_RED',
    URGENT: 'URGENT',
    AGGREGATING: 'AGGREGATING',
    CONFLUENCE: 'CONFLUENCE',
    HOLD_ACTIVE: 'HOLD_ACTIVE',
    KILL_TRIGGERED: 'KILL_TRIGGERED',
    EXECUTING: 'EXECUTING',
    TP_HIT: 'TP_HIT',
    STOPPED_OUT: 'STOPPED_OUT',
    REPORTING: 'REPORTING'
};

export const GRID_SIZE = 60;

// User Calibrated Desk positions (gx, gy)
// Based on useAgentStore IDs:
// 1 = Researcher         (4, 2)
// 2 = OnChainAnalyst     (2, 10)
// 3 = WalletTracker      (6, 10)
// 4 = IntelAgent         (16, 10)
// 5 = SignalAggregator   (12, 10)
// 6 = MacroSentinel      (19, 6)
// 7 = RiskManager        (22, 10)
// 8 = TradingBot         (4, 7)
// 9 = PerformanceAnalyst (36, 6)
const DESK_SEATS = [
    { id: 1, gx: 4, gy: 2, label: 'Researcher' },
    { id: 2, gx: 2, gy: 10, label: 'OnChainAnalyst' },
    { id: 3, gx: 6, gy: 10, label: 'WalletTracker' },
    { id: 4, gx: 16, gy: 10, label: 'IntelAgent' },
    { id: 5, gx: 12, gy: 10, label: 'SignalAggregator' },
    { id: 6, gx: 19, gy: 6, label: 'MacroSentinel' },
    { id: 7, gx: 22, gy: 10, label: 'RiskManager' },
    { id: 8, gx: 4, gy: 7, label: 'TradingBot' },
    { id: 9, gx: 36, gy: 6, label: 'PerformanceAnalyst' },
];

export class OfficeState {
    constructor() {
        this.characters = new Map(); // agentId -> state
        this.seats = new Map(); // seatId -> configuration

        // Register all desks from grid positions
        for (const desk of DESK_SEATS) {
            this.registerSeat(desk.id, desk.gx, desk.gy);
        }

        // Spawn default characters at their desks
        for (let i = 1; i <= 9; i++) {
            this.addCharacter(i, i);
        }
    }

    registerSeat(id, gx, gy) {
        // Calculate world pixel coordinate from grid coordinate
        const x = gx * GRID_SIZE + (GRID_SIZE / 2);
        const y = gy * GRID_SIZE + (GRID_SIZE / 2);
        // Define monitor location slightly above the desk center
        const mx = x;
        const my = y - 20;
        this.seats.set(id, { gx, gy, x, y, mx, my, assigned: false });
    }

    addCharacter(id, seatId) {
        const seat = this.seats.get(seatId);
        if (!seat) return;

        this.characters.set(id, {
            id,
            x: seat.x,
            y: seat.y,
            seatId,
            state: CharacterState.IDLE,
            isActive: false,
            // Matrix materialization effect properties
            matrixEffect: 'spawn',
            matrixEffectTimer: 0,
            matrixEffectSeeds: Array.from({ length: 16 }, () => Math.random()),
        });
        seat.assigned = true;
    }

    setAgentState(id, isActive, newState = null) {
        const ch = this.characters.get(id);
        if (!ch) return;

        ch.isActive = isActive;
        if (newState) {
            ch.state = newState;
        } else {
            ch.state = isActive ? CharacterState.WORKING : CharacterState.IDLE;
        }
    }

    update(dt) {
        // Run logic per character
        for (const [id, ch] of this.characters.entries()) {
            // Handle Matrix Spawn Effect
            if (ch.matrixEffect === 'spawn') {
                ch.matrixEffectTimer += dt;
                if (ch.matrixEffectTimer >= 0.3) {
                    // Effect done
                    ch.matrixEffect = null;
                }
                continue; // Skip FSM while spawning
            }

            // TODO: Advanced FSM / BFS wander logic goes here for future phases
        }
    }
}

// Singleton pattern for the global game state outside React
export const officeState = new OfficeState();
