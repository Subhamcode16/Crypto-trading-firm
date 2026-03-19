/**
 * officeState.js — Central mutable game state (lives outside React)
 *
 * The Character FSM:
 *   WORKING  → types at desk (agent is active)
 *   IDLE     → standing, deciding next move
 *   WALK     → moving along a BFS path
 *
 * Wander Logic:
 *  - Inactive agents rest at desk, then wander 3-5 tiles, then return to seat.
 *  - Active agents always path back to their seat.
 */

import { findPath, getWalkableTiles } from './pathfinder.js';

// ─── Constants ──────────────────────────────────────────────────────────────

export const CharacterState = {
    IDLE: 'IDLE',
    WALK: 'WALK',
    WORKING: 'WORKING',
    // Trading-specific states (Phase 2)
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
    REPORTING: 'REPORTING',
};

export const GRID_SIZE = 60; // Pixel size of one grid cell

// Map dimensions in grid cells
const MAP_COLS = 42; // 2520 / 60
const MAP_ROWS = 18; // 1080 / 60

// Walk speed: time (seconds) to cross one grid cell
const WALK_SPEED = 0.28; // seconds/cell → fluid but not too slow

// Wander timers
const WANDER_TIMER_MIN = 4;   // seconds before first wander after going idle
const WANDER_TIMER_MAX = 12;
const SEAT_REST_MIN = 8;   // seconds at desk after returning from wander
const SEAT_REST_MAX = 20;
const WANDER_LIMIT_MIN = 2;   // how many wander moves before returning to seat
const WANDER_LIMIT_MAX = 4;

// ─── Desk Seat Registry ─────────────────────────────────────────────────────

// User Calibrated Desk positions (gx, gy)
// Based on useAgentStore IDs:
// 1 = Researcher         (26, 3)
// 2 = OnChainAnalyst     (2, 11)
// 3 = WalletTracker      (6, 11)
// 4 = IntelAgent         (16, 11)
// 5 = SignalAggregator   (19, 7)
// 6 = MacroSentinel      (4, 3)
// 7 = RiskManager        (22, 11)
// 8 = TradingBot         (4, 8)
// 9 = PerformanceAnalyst (36.5, 7)
const DESK_SEATS = [
    { id: 1, gx: 26, gy: 3, label: 'Researcher', bounds: { minC: 24, maxC: 28, minR: 2, maxR: 4 } },
    { id: 2, gx: 2, gy: 11, label: 'OnChainAnalyst', bounds: { minC: 1, maxC: 4, minR: 10, maxR: 12 } },
    { id: 3, gx: 6, gy: 11, label: 'WalletTracker', bounds: { minC: 5, maxC: 8, minR: 10, maxR: 12 } },
    { id: 4, gx: 16, gy: 11, label: 'IntelAgent', bounds: { minC: 14, maxC: 18, minR: 10, maxR: 12 } },
    { id: 5, gx: 19, gy: 7, label: 'SignalAggregator', bounds: { minC: 17, maxC: 21, minR: 6, maxR: 8 } },
    { id: 6, gx: 4, gy: 3, label: 'MacroSentinel', bounds: { minC: 2, maxC: 8, minR: 2, maxR: 4 } },
    { id: 7, gx: 22, gy: 11, label: 'RiskManager', bounds: { minC: 20, maxC: 24, minR: 10, maxR: 12 } },
    { id: 8, gx: 4, gy: 8, label: 'TradingBot', bounds: { minC: 2, maxC: 6, minR: 7, maxR: 9 } },
    { id: 9, gx: 36.5, gy: 7, label: 'PerformanceAnalyst', bounds: { minC: 34, maxC: 39, minR: 5, maxR: 9 } },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function rand(min, max) {
    return min + Math.random() * (max - min);
}

function randInt(min, max) {
    return Math.floor(rand(min, max + 1));
}

// ─── OfficeState Class ───────────────────────────────────────────────────────

export class OfficeState {
    constructor() {
        this.characters = new Map(); // agentId → Character
        this.seats = new Map(); // seatId  → Seat

        // Build blocked tiles from desk seat footprints (1 tile each)
        this.blockedTiles = new Set();
        this.walkableTilesList = []; // pre-computed for wander targets

        // Interactive selection state
        this.selectedAgentId = null;
        this.hoveredAgentId = null;
        this.cameraFollowId = null;

        // Register all desks
        for (const desk of DESK_SEATS) {
            this.registerSeat(desk.id, desk.gx, desk.gy, desk.label, desk.bounds);
        }

        // Pre-compute walkable tiles (exclude desk cells)
        this._rebuildWalkable();

        // Spawn all 9 agents at their desks
        for (let i = 1; i <= 9; i++) {
            this.addCharacter(i, i);
        }
    }

    // ── Setup ────────────────────────────────────────────────────────────────

    registerSeat(id, gx, gy, label = '', bounds = null) {
        const col = Math.round(gx); // snap to nearest int for grid
        const row = Math.round(gy);
        // World pixel center of the desk cell
        const x = gx * GRID_SIZE + GRID_SIZE / 2;
        const y = gy * GRID_SIZE + GRID_SIZE / 2;
        // Monitor pixel position (slightly above desk center)
        const mx = x;
        const my = y - 20;

        this.seats.set(id, { id, gx, gy, col, row, x, y, mx, my, label, bounds, assigned: false });

        // Mark the desk tile as blocked for pathfinding
        this.blockedTiles.add(`${col},${row}`);
    }

    _rebuildWalkable() {
        this.walkableTilesList = getWalkableTiles(MAP_COLS, MAP_ROWS, this.blockedTiles);
    }

    addCharacter(id, seatId) {
        const seat = this.seats.get(seatId);
        if (!seat) return;

        const ch = {
            id,
            seatId,
            // Pixel world position
            x: seat.x,
            y: seat.y,
            // Grid tile position (for pathfinding)
            col: seat.col,
            row: seat.row,
            // Movement interpolation
            path: [],          // [{col, row}, ...] remaining steps
            moveProgress: 0,   // 0→1 progress across current tile
            prevX: seat.x,
            prevY: seat.y,
            nextX: seat.x,
            nextY: seat.y,
            // FSM
            state: CharacterState.IDLE,
            isActive: false,
            // Wander brain
            wanderTimer: rand(WANDER_TIMER_MIN, WANDER_TIMER_MAX),
            wanderCount: 0,
            wanderLimit: randInt(WANDER_LIMIT_MIN, WANDER_LIMIT_MAX),
            seatRestTimer: 0,  // rest at seat after returning from wander
            // Facing direction for renderer (left/right)
            facing: 'down',
            // Matrix materialization effect
            matrixEffect: 'spawn',
            matrixEffectTimer: 0,
            matrixEffectSeeds: Array.from({ length: 16 }, () => Math.random()),
            // Trading state animation
            animTimer: 0,      // counts up while in a special state
            // Speech bubble
            bubble: null,      // { type: 'alert'|'wait'|'signal'|'urgent', text, timer, maxTime }
        };

        this.characters.set(id, ch);
        seat.assigned = true;
    }

    // ── Public API ───────────────────────────────────────────────────────────

    /** Triggers a speech bubble on a character */
    triggerBubble(agentId, type, text, duration = 3.0) {
        const ch = this.characters.get(agentId);
        if (!ch) return;
        ch.bubble = { type, text, timer: duration, maxTime: duration };
    }

    /** Dismiss a bubble (e.g. on permission granted) */
    clearBubble(agentId) {
        const ch = this.characters.get(agentId);
        if (ch) ch.bubble = null;
    }

    /** Select an agent by click (or deselect if same id again) */
    selectAgent(agentId) {
        if (this.selectedAgentId === agentId) {
            this.selectedAgentId = null;
            this.cameraFollowId = null;
        } else {
            this.selectedAgentId = agentId;
            this.cameraFollowId = agentId; // follow on select
        }
    }

    /** Set hovered agent (from pointer move hit test) */
    hoverAgent(agentId) {
        this.hoveredAgentId = agentId;
    }

    /**
     * Hit-test a world-space point against all agent sprites.
     * Returns the agentId of the topmost hit, or null.
     */
    hitTestAgent(worldX, worldY, spriteSize = 32) {
        const half = spriteSize;
        let topHit = null;
        let topY = -Infinity;
        for (const [id, ch] of this.characters) {
            if (ch.matrixEffect) continue;
            if (
                worldX >= ch.x - half && worldX <= ch.x + half &&
                worldY >= ch.y - half * 2 && worldY <= ch.y
            ) {
                if (ch.y > topY) { topY = ch.y; topHit = id; }
            }
        }
        return topHit;
    }

    /** Called from GameContainer when Zustand agent state changes */
    setAgentState(id, isActive, newState = null) {
        const ch = this.characters.get(id);
        if (!ch) return;

        const wasActive = ch.isActive;
        ch.isActive = isActive;

        if (newState) {
            ch.state = newState;
        } else if (isActive && !wasActive) {
            // Agent just became active → path to desk immediately
            ch.state = CharacterState.WALK;
            this._pathToSeat(ch);
        } else if (!isActive && wasActive) {
            // Agent went idle → allow them to finish typing, then wander
            // Reset wander timers
            ch.wanderTimer = rand(WANDER_TIMER_MIN, WANDER_TIMER_MAX);
            ch.wanderCount = 0;
            ch.wanderLimit = randInt(WANDER_LIMIT_MIN, WANDER_LIMIT_MAX);
        }
    }

    // ── Update Loop ──────────────────────────────────────────────────────────

    // ── Update Loop ──────────────────────────────────────────────────────────

    update(dt) {
        for (const [, ch] of this.characters) {

            // ── Tick animation timer ─────────────────────────────────────────
            ch.animTimer += dt;

            // ── Tick speech bubble ───────────────────────────────────────────
            if (ch.bubble) {
                ch.bubble.timer -= dt;
                if (ch.bubble.timer <= 0) ch.bubble = null;
            }

            if (ch.matrixEffect === 'spawn') {
                ch.matrixEffectTimer += dt;
                if (ch.matrixEffectTimer >= 0.3) {
                    ch.matrixEffect = null;
                    ch.state = ch.isActive ? CharacterState.WORKING : CharacterState.IDLE;
                }
                continue; // Skip FSM while spawning
            }

            // ── Movement Advance (Independent of State) ──────────────────────
            // Advance path if it exists, regardless of current FSM state
            if (ch.path.length > 0) {
                this._stepMovement(ch, dt);
            }

            // ── FSM Logic ────────────────────────────────────────────────────
            switch (ch.state) {

                case CharacterState.WORKING:
                    // If isActive is false, they should go idle
                    if (!ch.isActive) {
                        ch.state = CharacterState.IDLE;
                        ch.wanderTimer = rand(WANDER_TIMER_MIN, WANDER_TIMER_MAX);
                        break;
                    }
                    // Enforcement: If active but disconnected from desk, path back
                    if (ch.path.length === 0 && !this._isAtSeat(ch)) {
                        this._pathToSeat(ch);
                    }
                    break;

                case CharacterState.IDLE:
                    if (ch.isActive) {
                        // Became active while idle → head to desk
                        ch.state = CharacterState.WALK;
                        this._pathToSeat(ch);
                        break;
                    }
                    // Idle countdown for roaming
                    ch.wanderTimer -= dt;
                    if (ch.wanderTimer <= 0) {
                        if (ch.wanderCount >= ch.wanderLimit) {
                            // Return to seat to rest
                            ch.state = CharacterState.WALK;
                            this._pathToSeat(ch);
                            ch.wanderCount = 0;
                            ch.wanderLimit = randInt(WANDER_LIMIT_MIN, WANDER_LIMIT_MAX);
                        } else {
                            // Roam to random tile
                            ch.state = CharacterState.WALK;
                            this._pathToRandom(ch);
                            ch.wanderCount++;
                        }
                    }
                    break;

                case CharacterState.WALK:
                    // Mid-walk activation: if they were roaming, divert to desk
                    if (ch.isActive && !this._pathLeadsToSeat(ch)) {
                        this._pathToSeat(ch);
                    }
                    break;

                default:
                    // Special Trading States (SIGNAL_FOUND, CONFLUENCE, etc.)
                    // Ensure active agents path back even while displaying special effects
                    if (ch.isActive && ch.path.length === 0 && !this._isAtSeat(ch)) {
                        this._pathToSeat(ch);
                    }
                    // If they go inactive during a special state, revert to IDLE
                    if (!ch.isActive) {
                        ch.state = CharacterState.IDLE;
                    }
                    break;
            }
        }
    }

    // ── Movement Helpers ─────────────────────────────────────────────────────

    _stepMovement(ch, dt) {
        if (ch.path.length === 0) return;

        // Advance moveProgress
        ch.moveProgress += dt / WALK_SPEED;

        if (ch.moveProgress >= 1) {
            // Snap to next tile
            const next = ch.path.shift();
            ch.col = next.col;
            ch.row = next.row;
            ch.x = next.col * GRID_SIZE + GRID_SIZE / 2;
            ch.y = next.row * GRID_SIZE + GRID_SIZE / 2;
            ch.prevX = ch.x;
            ch.prevY = ch.y;

            if (ch.path.length > 0) {
                const upcoming = ch.path[0];
                ch.nextX = upcoming.col * GRID_SIZE + GRID_SIZE / 2;
                ch.nextY = upcoming.row * GRID_SIZE + GRID_SIZE / 2;
                // Update facing
                const dx = ch.nextX - ch.x;
                const dy = ch.nextY - ch.y;
                if (Math.abs(dx) > Math.abs(dy)) {
                    ch.facing = dx > 0 ? 'right' : 'left';
                } else {
                    ch.facing = dy > 0 ? 'down' : 'up';
                }
            } else {
                // ARRIVAL
                const atSeat = this._isAtSeat(ch);
                if (atSeat) {
                    // Only overwrite state if we aren't in a high-priority trading state
                    if (ch.state === CharacterState.WALK || ch.state === CharacterState.IDLE) {
                        ch.state = ch.isActive ? CharacterState.WORKING : CharacterState.IDLE;
                    }
                    // Reset rest timer if we arrived at seat while idle
                    if (!ch.isActive) {
                        ch.wanderTimer = rand(SEAT_REST_MIN, SEAT_REST_MAX);
                    }
                    // Snap position precisely to seat
                    const seat = this.seats.get(ch.seatId);
                    ch.x = seat.x;
                    ch.y = seat.y;
                    ch.col = seat.col;
                    ch.row = seat.row;
                } else {
                    // Finished a wander step
                    ch.state = CharacterState.IDLE;
                    ch.wanderTimer = rand(WANDER_TIMER_MIN / 2, WANDER_TIMER_MAX / 2);
                }
            }
            ch.moveProgress = 0;
        } else {
            // Lerp between prevX/Y and nextX/Y
            const t = ch.moveProgress;
            ch.x = ch.prevX + (ch.nextX - ch.prevX) * t;
            ch.y = ch.prevY + (ch.nextY - ch.prevY) * t;
        }
    }

    _pathToSeat(ch) {
        const seat = this.seats.get(ch.seatId);
        if (!seat) return;

        // Temporarily unblock the agent's own seat so they can path to it
        const seatKey = `${seat.col},${seat.row}`;
        this.blockedTiles.delete(seatKey);
        const path = findPath(ch.col, ch.row, seat.col, seat.row, this.blockedTiles, MAP_COLS, MAP_ROWS);
        this.blockedTiles.add(seatKey);

        ch.path = path;
        ch.moveProgress = 0;

        if (path.length > 0) {
            ch.prevX = ch.x;
            ch.prevY = ch.y;
            ch.nextX = path[0].col * GRID_SIZE + GRID_SIZE / 2;
            ch.nextY = path[0].row * GRID_SIZE + GRID_SIZE / 2;
        }
    }

    _pathToRandom(ch) {
        if (this.walkableTilesList.length === 0) return;

        // Find the designated room bounds for this agent's seat
        const seat = this.seats.get(ch.seatId);
        const bounds = seat?.bounds || { minC: 0, maxC: MAP_COLS - 1, minR: 0, maxR: MAP_ROWS - 1 };

        // Restrict to tiles within their assigned room bounds
        const roomTiles = this.walkableTilesList.filter(t => {
            return t.col >= bounds.minC && t.col <= bounds.maxC &&
                   t.row >= bounds.minR && t.row <= bounds.maxR;
        });

        // Fallback to all walkable tiles if room logic fails
        const basePool = roomTiles.length > 0 ? roomTiles : this.walkableTilesList;

        // Pick a random walkable tile (within 8 cells radius for realism, bounded to room)
        const nearby = basePool.filter(t => {
            const dc = Math.abs(t.col - ch.col);
            const dr = Math.abs(t.row - ch.row);
            return dc <= 8 && dr <= 8 && (dc + dr) >= 1; // not precisely the same spot
        });

        const pool = nearby.length > 0 ? nearby : basePool;
        const target = pool[Math.floor(Math.random() * pool.length)];

        const path = findPath(ch.col, ch.row, target.col, target.row, this.blockedTiles, MAP_COLS, MAP_ROWS);
        ch.path = path;
        ch.moveProgress = 0;

        if (path.length > 0) {
            ch.prevX = ch.x;
            ch.prevY = ch.y;
            ch.nextX = path[0].col * GRID_SIZE + GRID_SIZE / 2;
            ch.nextY = path[0].row * GRID_SIZE + GRID_SIZE / 2;
        } else {
            // No path found, just idle again
            ch.state = CharacterState.IDLE;
            ch.wanderTimer = rand(WANDER_TIMER_MIN, WANDER_TIMER_MAX);
        }
    }

    // ── Utility ──────────────────────────────────────────────────────────────

    _isAtSeat(ch) {
        const seat = this.seats.get(ch.seatId);
        return seat && ch.col === seat.col && ch.row === seat.row;
    }

    _pathLeadsToSeat(ch) {
        if (ch.path.length === 0) return false;
        const last = ch.path[ch.path.length - 1];
        const seat = this.seats.get(ch.seatId);
        return seat && last.col === seat.col && last.row === seat.row;
    }
}

// Singleton — lives outside React for performance
export const officeState = new OfficeState();
