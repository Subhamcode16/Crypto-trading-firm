import React, { useEffect, useRef, useState } from 'react';
import { OfficeCanvas } from './OfficeCanvas';
import { ToolOverlay } from './ToolOverlay';
import { startGameLoop } from '../../engine/gameLoop';
import { Renderer } from '../../engine/renderer';
import { officeState } from '../../engine/officeState';
import { useAgentStore } from '../../stores/useAgentStore';
import { useSystemStore } from '../../stores/useSystemStore';

// Camera follow lerp factor (0.08 = smooth, 1.0 = instant)
const CAMERA_LERP = 0.08;
const CAMERA_SNAP_THRESHOLD = 0.5; // px — snap when this close

export function GameContainer() {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    const renderer = React.useMemo(() => new Renderer(), []);
    const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });

    // Pan and Zoom
    const panRef = useRef({ x: 0, y: 0 });
    const zoom = useSystemStore((state) => state.zoom);
    const zoomRef = useRef(zoom);
    
    // Keep zoomRef in sync for the non-reactive loop
    useEffect(() => {
        zoomRef.current = zoom;
    }, [zoom]);

    // Cursor style: change to pointer when hovering an agent
    const [cursor, setCursor] = useState('crosshair');

    const agents = useAgentStore((state) => state.agents);

    // Sync Zustand Agents → OfficeState and Global Names
    useEffect(() => {
        const names = {};
        Object.values(agents).forEach(agent => {
            names[agent.id] = agent.name;
            officeState.setAgentState(agent.id, agent.status !== 'IDLE');
        });
        window.__AGENT_NAMES = names;
    }, [agents]);

    // Handle full screen resize
    useEffect(() => {
        const obs = new ResizeObserver((entries) => {
            for (let entry of entries) {
                setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
            }
        });
        if (containerRef.current) obs.observe(containerRef.current);
        return () => obs.disconnect();
    }, []);

    // Start Game Loop
    useEffect(() => {
        if (!canvasRef.current) return;

        const renderer = new Renderer();

        const callbacks = {
            update: (dt) => {
                officeState.update(dt);

                // ── Phase 3: Camera Follow ──────────────────────────────────────
                if (officeState.cameraFollowId !== null) {
                    const followCh = officeState.characters.get(officeState.cameraFollowId);
                    if (followCh) {
                        // Target pan that centers the character in the viewport
                        const targetX = dimensions.width / 2 / zoomRef.current - followCh.x;
                        const targetY = dimensions.height / 2 / zoomRef.current - followCh.y;

                        const dx = targetX - panRef.current.x;
                        const dy = targetY - panRef.current.y;

                        if (Math.abs(dx) < CAMERA_SNAP_THRESHOLD && Math.abs(dy) < CAMERA_SNAP_THRESHOLD) {
                            panRef.current.x = targetX;
                            panRef.current.y = targetY;
                        } else {
                            panRef.current.x += dx * CAMERA_LERP;
                            panRef.current.y += dy * CAMERA_LERP;
                        }
                    }
                }
            },
            render: (ctx) => {
                renderer.renderFrame(ctx, dimensions.width, dimensions.height, panRef.current, zoomRef.current);
            }
        };

        const cleanup = startGameLoop(canvasRef.current, callbacks);
        return cleanup;
    }, [dimensions]);

    // ── World Space Helper ────────────────────────────────────────────────────
    const toWorld = (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const cssX = e.clientX - rect.left;
        const cssY = e.clientY - rect.top;
        return {
            worldX: (cssX / zoomRef.current) - panRef.current.x,
            worldY: (cssY / zoomRef.current) - panRef.current.y,
        };
    };

    // ── Pan Input ─────────────────────────────────────────────────────────────
    const handlePointerMove = (e) => {
        if (e.buttons === 1) {
            // Cancel camera follow when user pans manually
            officeState.cameraFollowId = null;
            panRef.current.x += e.movementX / zoomRef.current;
            panRef.current.y += e.movementY / zoomRef.current;
        }

        // ── Phase 3: Hover Hit Test ────────────────────────────────────────────
        const { worldX, worldY } = toWorld(e);
        const hit = officeState.hitTestAgent(worldX, worldY);
        officeState.hoverAgent(hit);
        setCursor(hit !== null ? 'pointer' : 'crosshair');
    };

    // ── Phase 3: Click to Select ──────────────────────────────────────────────
    const handlePointerClick = (e) => {
        if (e.button !== 0) return; // Left click only
        const { worldX, worldY } = toWorld(e);
        const hit = officeState.hitTestAgent(worldX, worldY);
        if (hit !== null) {
            officeState.selectAgent(hit);
        } else {
            // Click on empty space — deselect and stop following
            officeState.selectedAgentId = null;
            officeState.cameraFollowId = null;
        }
    };

    return (
        <div
            ref={containerRef}
            className="absolute inset-0 w-full h-full overflow-hidden"
            style={{ cursor }}
            onPointerMove={handlePointerMove}
            onClick={handlePointerClick}
        >
            <OfficeCanvas
                ref={canvasRef}
                width={dimensions.width}
                height={dimensions.height}
            />
            <ToolOverlay pan={panRef.current} zoom={zoom} />
        </div>
    );
}
