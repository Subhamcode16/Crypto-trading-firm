import React, { useEffect, useRef, useState } from 'react';
import { OfficeCanvas } from './OfficeCanvas';
import { ToolOverlay } from './ToolOverlay';
import { startGameLoop } from '../../engine/gameLoop';
import { Renderer } from '../../engine/renderer';
import { officeState } from '../../engine/officeState';
import { useAgentStore } from '../../stores/useAgentStore';

export function GameContainer() {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });

    // Pan and Zoom
    const panRef = useRef({ x: 0, y: 0 });
    const zoom = 1.2;

    const agents = useAgentStore((state) => state.agents);

    // Sync Zustand Agents -> OfficeState and Global Names
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
            },
            render: (ctx) => {
                renderer.renderFrame(ctx, dimensions.width, dimensions.height, panRef.current, zoom);
            }
        };

        const cleanup = startGameLoop(canvasRef.current, callbacks);
        return cleanup;
    }, [dimensions]);

    // Pan Input Handling
    const handlePointerMove = (e) => {
        if (e.buttons === 1) { // Left click drag
            panRef.current.x += e.movementX / zoom;
            panRef.current.y += e.movementY / zoom;
        }
        // Debug: track world coords
        const rect = e.currentTarget.getBoundingClientRect();
        const cssX = e.clientX - rect.left;
        const cssY = e.clientY - rect.top;
        const worldX = Math.round((cssX - panRef.current.x) / zoom);
        const worldY = Math.round((cssY - panRef.current.y) / zoom);
    };

    return (
        <div
            ref={containerRef}
            className="absolute inset-0 w-full h-full overflow-hidden cursor-crosshair"
            onPointerMove={handlePointerMove}
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
