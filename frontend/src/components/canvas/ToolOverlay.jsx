import React, { useEffect, useState } from 'react';
import { officeState, CharacterState } from '../../engine/officeState';

// State badge styling map - visual coding for each FSM state
const STATE_STYLES = {
    [CharacterState.IDLE]: { label: 'IDLE', bg: 'bg-gray-300', text: 'text-gray-700', dot: 'bg-gray-400', pulse: false },
    [CharacterState.WALK]: { label: 'WALKING', bg: 'bg-blue-100', text: 'text-blue-700', dot: 'bg-blue-400', pulse: true },
    [CharacterState.WORKING]: { label: 'WORKING', bg: 'bg-white/90', text: 'text-gray-800', dot: 'bg-green-400', pulse: true },
    [CharacterState.SIGNAL_FOUND]: { label: 'SIGNAL!', bg: 'bg-yellow-100', text: 'text-yellow-800', dot: 'bg-yellow-400', pulse: true },
    [CharacterState.VERIFYING]: { label: 'VERIFYING', bg: 'bg-blue-100', text: 'text-blue-800', dot: 'bg-blue-500', pulse: true },
    [CharacterState.STAMPING_GREEN]: { label: '✓ CLEARED', bg: 'bg-green-100', text: 'text-green-800', dot: 'bg-green-500', pulse: false },
    [CharacterState.STAMPING_RED]: { label: '✗ KILLED', bg: 'bg-red-100', text: 'text-red-800', dot: 'bg-red-500', pulse: false },
    [CharacterState.URGENT]: { label: '! URGENT', bg: 'bg-orange-100', text: 'text-orange-800', dot: 'bg-orange-500', pulse: true },
    [CharacterState.AGGREGATING]: { label: 'AGGREGATING', bg: 'bg-purple-100', text: 'text-purple-800', dot: 'bg-purple-400', pulse: true },
    [CharacterState.CONFLUENCE]: { label: '★ CONFLUENCE', bg: 'bg-purple-200', text: 'text-purple-900', dot: 'bg-purple-600', pulse: true },
    [CharacterState.HOLD_ACTIVE]: { label: '⏸ HOLD', bg: 'bg-amber-100', text: 'text-amber-900', dot: 'bg-amber-500', pulse: true },
    [CharacterState.KILL_TRIGGERED]: { label: '☠ KILL', bg: 'bg-red-200', text: 'text-red-900', dot: 'bg-red-600', pulse: true },
    [CharacterState.EXECUTING]: { label: '▶ EXECUTING', bg: 'bg-emerald-100', text: 'text-emerald-900', dot: 'bg-emerald-500', pulse: true },
    [CharacterState.TP_HIT]: { label: '🎯 TP HIT', bg: 'bg-green-200', text: 'text-green-900', dot: 'bg-green-600', pulse: false },
    [CharacterState.STOPPED_OUT]: { label: '📉 STOPPED', bg: 'bg-red-100', text: 'text-red-800', dot: 'bg-red-500', pulse: false },
    [CharacterState.REPORTING]: { label: '📋 REPORT', bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-300', pulse: false },
};

export function ToolOverlay({ pan, zoom }) {
    const [, setTick] = useState(0);

    useEffect(() => {
        let rafId;
        const tick = () => {
            setTick(n => n + 1);
            rafId = requestAnimationFrame(tick);
        };
        rafId = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(rafId);
    }, []);

    const dpr = window.devicePixelRatio || 1;
    const overlays = [];

    for (const [id, ch] of officeState.characters.entries()) {
        if (ch.matrixEffect === 'spawn') continue;

        const screenX = (ch.x + pan.x) * zoom;
        const screenY = (ch.y + pan.y - 60) * zoom;

        const style = STATE_STYLES[ch.state] || STATE_STYLES[CharacterState.IDLE];

        // Only show overlay if agent is active or has a notable state
        const showBadge = true; // Always show static name tag

        overlays.push(
            <div
                key={`overlay-${id}`}
                className="absolute transform -translate-[50%] pointer-events-none"
                style={{
                    left: `${screenX}px`,
                    top: `${screenY}px`,
                    zIndex: 10 + Math.round(ch.y)
                }}
            >
                {showBadge && (
                    <div className="flex flex-col items-center">
                        <div className="bg-black/70 px-1.5 py-0.5 rounded-[2px] border border-white/20">
                            <span className="text-[8px] pixel-font uppercase tracking-widest text-white whitespace-nowrap shadow-[1px_1px_0_rgba(0,0,0,1)]">
                                {window.__AGENT_NAMES?.[id] || `AGT-${id}`}
                            </span>
                        </div>
                        {/* Status indicator dot below the name */}
                        <div className={`mt-1 w-1.5 h-1.5 rounded-full border border-black shadow-[inset_1px_1px_2px_rgba(255,255,255,0.7)] ${ch.isActive ? 'bg-green-400' : 'bg-gray-500'}`} />
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
            {overlays}
        </div>
    );
}
