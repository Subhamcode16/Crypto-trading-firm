import { officeState, CharacterState, GRID_SIZE } from './officeState';

// Disable grid rendering after calibration
window.__DEBUG_GRID = false;

const CHARACTER_Z_SORT_OFFSET = 0.5;
const MATRIX_EFFECT_DURATION = 0.3;

export class Renderer {
    constructor() {
        this.sprites = {}; // Image caches
        this.backgroundLoaded = false;
        this.bgImage = new Image();
        this.bgImage.src = '/assets/tilesets/office_rpg_map_extended.png';
        this.bgImage.onload = () => { this.backgroundLoaded = true; };

        // Preload 9 agent characters
        for (let i = 1; i <= 9; i++) {
            const img = new Image();
            img.src = `/assets/sprites/agent${i}.png`;
            this.sprites[i] = img;
        }
    }

    renderFrame(ctx, canvasWidth, canvasHeight, pan, zoom) {
        const dpr = window.devicePixelRatio || 1;

        // 1. Clear Canvas (with dark background representing void)
        ctx.fillStyle = '#011301';
        ctx.fillRect(0, 0, canvasWidth * dpr, canvasHeight * dpr);

        if (!this.backgroundLoaded) return;

        // Apply global transform (pan / zoom)
        ctx.save();

        // Scale to device pixel ratio AND game zoom level
        ctx.scale(dpr * zoom, dpr * zoom);

        // Apply pan translation
        ctx.translate(pan.x, pan.y);

        // 2. Draw Office Layout (Base layer)
        // Draw the 2520x1080 pure pixel art base map
        ctx.drawImage(this.bgImage, 0, 0, 2520, 1080);

        // Render background grid if debug is enabled
        if (window.__DEBUG_GRID) {
            this.renderGrid(ctx, 2520, 1080);
        }

        // 3. Collect & Z-Sort Drawables
        const drawables = [];
        const now = performance.now() / 1000; // seconds, for animations

        for (const [id, ch] of officeState.characters.entries()) {
            const sprite = this.sprites[id];
            if (!sprite || !sprite.complete) continue;

            const scale = 2.0;
            const sprW = sprite.width * scale;
            const sprH = sprite.height * scale;

            // Walking bob: small vertical oscillation when moving
            const isWalking = ch.state === CharacterState.WALK;
            const bob = isWalking ? Math.sin(now * 12) * 1.5 : 0;

            // World draw position — center horizontally, anchor bottom to ch.y
            const drawX = ch.x - sprW / 2;
            const drawY = ch.y - sprH + 20 + bob;

            const seat = officeState.seats.get(ch.seatId);
            const isAtDesk = ch.state === CharacterState.WORKING;

            // Monitor Glow (only when active at desk)
            if (seat && ch.isActive && isAtDesk) {
                drawables.push({
                    zY: seat.my,
                    draw: (context) => {
                        context.save();
                        context.globalCompositeOperation = 'screen';
                        const isWarning = [
                            CharacterState.URGENT, CharacterState.HOLD_ACTIVE,
                            CharacterState.STAMPING_RED, CharacterState.KILL_TRIGGERED,
                            CharacterState.STOPPED_OUT
                        ].includes(ch.state);
                        const colorHex = isWarning
                            ? 'rgba(217, 119, 6, 0.4)'
                            : 'rgba(16, 185, 129, 0.4)';
                        const g = context.createRadialGradient(seat.mx, seat.my, 5, seat.mx, seat.my, 40);
                        g.addColorStop(0, colorHex);
                        g.addColorStop(1, 'rgba(0,0,0,0)');
                        context.fillStyle = g;
                        context.fillRect(seat.mx - 40, seat.my - 40, 80, 80);
                        context.restore();
                    }
                });
            }

            // ── Phase 3: Selection / Hover Outline ───────────────────────────
            const isSelected = officeState.selectedAgentId === id;
            const isHovered = officeState.hoveredAgentId === id;

            if ((isSelected || isHovered) && !ch.matrixEffect) {
                drawables.push({
                    zY: ch.y + CHARACTER_Z_SORT_OFFSET - 0.001, // just below character
                    draw: (context) => {
                        context.save();
                        const alpha = isSelected ? 1.0 : 0.5;
                        context.globalAlpha = alpha;
                        context.globalCompositeOperation = 'source-over';

                        // Pixel-style outline: draw sprite shifted in 4 directions in white
                        const offsets = [[-2, 0], [2, 0], [0, -2], [0, 2]];
                        // Tint: create a white version by drawing on top with compositing
                        for (const [ox, oy] of offsets) {
                            context.filter = 'brightness(10)';
                            if (isAtDesk) {
                                context.save();
                                context.beginPath();
                                context.rect(drawX + ox, drawY + oy, sprW, sprH * 0.70);
                                context.clip();
                                context.drawImage(sprite, drawX + ox, drawY + oy, sprW, sprH);
                                context.restore();
                            } else {
                                context.drawImage(sprite, drawX + ox, drawY + oy, sprW, sprH);
                            }
                        }
                        context.filter = 'none';

                        // Selected: pulsing outer glow ring
                        if (isSelected) {
                            const pulse = 0.3 + 0.2 * Math.sin(now * 4);
                            const glow = context.createRadialGradient(ch.x, ch.y - sprH * 0.3, 2, ch.x, ch.y - sprH * 0.3, sprW * 0.7);
                            glow.addColorStop(0, `rgba(255,255,255,${pulse})`);
                            glow.addColorStop(1, 'rgba(255,255,255,0)');
                            context.globalCompositeOperation = 'screen';
                            context.fillStyle = glow;
                            context.fillRect(drawX - 10, drawY - 10, sprW + 20, sprH + 20);
                        }
                        context.restore();
                    }
                });
            }

            // Character sprite
            drawables.push({
                zY: ch.y + CHARACTER_Z_SORT_OFFSET,
                draw: (context) => {
                    if (ch.matrixEffect) {
                        this.renderMatrixEffect(context, sprite, drawX, drawY, scale, ch);
                    } else if (isAtDesk) {
                        // Clip lower body so agent appears seated behind desk
                        context.save();
                        context.beginPath();
                        context.rect(drawX, drawY, sprW, sprH * 0.70);
                        context.clip();
                        context.drawImage(sprite, drawX, drawY, sprW, sprH);
                        context.restore();
                    } else {
                        // Walking or idle — draw full sprite, slight transparency when idle
                        context.save();
                        context.globalAlpha = ch.state === CharacterState.IDLE ? 0.9 : 1.0;
                        context.drawImage(sprite, drawX, drawY, sprW, sprH);
                        context.restore();
                    }
                }
            });

            // ── Phase 2: State Aura Effect ────────────────────────────────────
            // Pushed AFTER the character so it renders on top in sorted order
            const hasStateEffect = [
                CharacterState.SIGNAL_FOUND, CharacterState.URGENT,
                CharacterState.KILL_TRIGGERED, CharacterState.EXECUTING,
                CharacterState.TP_HIT, CharacterState.STOPPED_OUT,
                CharacterState.CONFLUENCE, CharacterState.STAMPING_GREEN,
                CharacterState.STAMPING_RED, CharacterState.HOLD_ACTIVE,
                CharacterState.VERIFYING, CharacterState.AGGREGATING,
                CharacterState.REPORTING,
            ].includes(ch.state);

            if (hasStateEffect) {
                drawables.push({
                    zY: ch.y + CHARACTER_Z_SORT_OFFSET + 0.01, // always above character
                    draw: (context) => {
                        this.renderStateEffect(context, ch, now);
                    }
                });
            }
        }

        // Sort by Y depth
        drawables.sort((a, b) => a.zY - b.zY);
        for (const d of drawables) d.draw(ctx);

        // ── Phase 2: Speech Bubbles (always on top of everything) ─────────────
        for (const [id, ch] of officeState.characters.entries()) {
            if (ch.bubble && !ch.matrixEffect) {
                const sprite = this.sprites[id];
                const sprH = sprite ? sprite.height * 2.0 : 48;
                this.renderBubble(ctx, ch, sprH, now);
            }
        }

        ctx.restore();
    }

    /**
     * Renders a state-specific visual effect above/around an agent.
     * Each state has its own distinct visual language.
     */
    renderStateEffect(ctx, ch, now) {
        const x = ch.x;
        const y = ch.y - 60; // above agent head
        ctx.save();

        switch (ch.state) {
            case CharacterState.SIGNAL_FOUND: {
                // Pulsing yellow "!" icon with float animation
                const floatY = y - Math.sin(now * 4) * 6;
                const pulse = 0.7 + 0.3 * Math.sin(now * 8);
                ctx.globalAlpha = pulse;
                ctx.fillStyle = '#FACC15';
                ctx.font = 'bold 20px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('!', x, floatY);
                // Outer ring
                ctx.strokeStyle = 'rgba(250, 204, 21, 0.4)';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(x, y + 10, 18 + Math.sin(now * 5) * 3, 0, Math.PI * 2);
                ctx.stroke();
                break;
            }
            case CharacterState.URGENT: {
                // Flashing red urgent aura
                const alpha = 0.5 + 0.5 * Math.sin(now * 10);
                const g = ctx.createRadialGradient(x, ch.y, 5, x, ch.y, 35);
                g.addColorStop(0, `rgba(239,68,68,${alpha})`);
                g.addColorStop(1, 'rgba(239,68,68,0)');
                ctx.fillStyle = g;
                ctx.beginPath();
                ctx.arc(x, ch.y, 35, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = `rgba(239,68,68,${alpha})`;
                ctx.font = 'bold 11px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('URGENT', x, y - 4);
                break;
            }
            case CharacterState.KILL_TRIGGERED: {
                // Full red screen pulse + KILL text
                const ka = 0.4 + 0.4 * Math.abs(Math.sin(now * 12));
                const kg = ctx.createRadialGradient(x, ch.y, 0, x, ch.y, 50);
                kg.addColorStop(0, `rgba(220,38,38,${ka})`);
                kg.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = kg;
                ctx.beginPath();
                ctx.arc(x, ch.y, 50, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#ff2222';
                ctx.font = 'bold 12px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('KILL', x, y - 4);
                break;
            }
            case CharacterState.EXECUTING: {
                // Terminal flash — cyan scanline sweep
                const progress = (now % 1.0); // 0→1 every second
                ctx.globalAlpha = 0.8;
                ctx.fillStyle = '#22D3EE';
                ctx.fillRect(x - 20, ch.y - 40 + progress * 60, 40, 2);
                ctx.globalAlpha = 0.4;
                ctx.strokeStyle = '#22D3EE';
                ctx.lineWidth = 1;
                ctx.strokeRect(x - 20, ch.y - 40, 40, 60);
                break;
            }
            case CharacterState.TP_HIT: {
                // Gold celebrate burst
                const angle = (now * 3) % (Math.PI * 2);
                for (let i = 0; i < 6; i++) {
                    const a = angle + (i / 6) * Math.PI * 2;
                    const r = 20 + Math.sin(now * 6 + i) * 5;
                    ctx.fillStyle = i % 2 === 0 ? '#FACC15' : '#FDE68A';
                    ctx.beginPath();
                    ctx.arc(x + Math.cos(a) * r, ch.y - 10 + Math.sin(a) * r * 0.5, 3, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.fillStyle = '#FACC15';
                ctx.font = 'bold 14px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('✓', x, y);
                break;
            }
            case CharacterState.STOPPED_OUT: {
                // Dark red slump / downward arrows
                const sa = 0.6 + 0.4 * Math.sin(now * 3);
                ctx.globalAlpha = sa;
                ctx.fillStyle = '#991B1B';
                ctx.font = 'bold 16px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('▼', x, y);
                break;
            }
            case CharacterState.HOLD_ACTIVE: {
                // Orange hold sign pulsing
                const ha = 0.7 + 0.3 * Math.sin(now * 5);
                ctx.globalAlpha = ha;
                ctx.fillStyle = '#F97316';
                ctx.font = 'bold 11px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('HOLD', x, y);
                ctx.strokeStyle = 'rgba(249,115,22,0.5)';
                ctx.lineWidth = 2;
                ctx.strokeRect(x - 20, y - 14, 40, 18);
                break;
            }
            case CharacterState.VERIFYING: {
                // Rotating search ring
                const va = (now * 2) % (Math.PI * 2);
                ctx.globalAlpha = 0.8;
                ctx.strokeStyle = '#60A5FA';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(x, y, 14, va, va + Math.PI * 1.5);
                ctx.stroke();
                ctx.fillStyle = '#93C5FD';
                ctx.font = '10px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('?', x, y + 4);
                break;
            }
            case CharacterState.CONFLUENCE:
            case CharacterState.AGGREGATING: {
                // Green cards flowing upward
                for (let i = 0; i < 3; i++) {
                    const cardY = y - ((now * 20 + i * 12) % 36);
                    const cardAlpha = 1 - ((now * 0.5 + i * 0.3) % 1);
                    ctx.globalAlpha = cardAlpha;
                    ctx.fillStyle = '#10B981';
                    ctx.fillRect(x - 5 + i * 5, cardY, 8, 5);
                }
                break;
            }
            case CharacterState.STAMPING_GREEN: {
                const sga = 0.7 + 0.3 * Math.sin(now * 6);
                ctx.globalAlpha = sga;
                ctx.fillStyle = '#22C55E';
                ctx.font = 'bold 18px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('✓', x, y);
                break;
            }
            case CharacterState.STAMPING_RED: {
                const sra = 0.7 + 0.3 * Math.sin(now * 6);
                ctx.globalAlpha = sra;
                ctx.fillStyle = '#EF4444';
                ctx.font = 'bold 18px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('✗', x, y);
                break;
            }
            case CharacterState.REPORTING: {
                // Paper/document float upward
                const rY = y - Math.sin(now * 2) * 4;
                ctx.fillStyle = '#E2E8F0';
                ctx.fillRect(x - 8, rY - 10, 16, 12);
                ctx.fillStyle = '#94A3B8';
                for (let i = 0; i < 3; i++) {
                    ctx.fillRect(x - 5, rY - 7 + i * 3, 10, 1);
                }
                break;
            }
        }

        ctx.restore();
    }

    /**
     * Renders a speech bubble above a character.
     * Type determines style: 'alert' (red), 'wait' (gray), 'signal' (yellow), 'urgent' (orange).
     */
    renderBubble(ctx, ch, sprH, now) {
        const bubble = ch.bubble;
        const bx = ch.x;
        const by = ch.y - sprH - 14;

        // Fade out in last 0.5s
        const fadeT = Math.min(bubble.timer / 0.5, 1.0);
        ctx.save();
        ctx.globalAlpha = fadeT;

        const COLORS = {
            alert: { bg: '#7F1D1D', border: '#EF4444', text: '#FCA5A5' },
            wait: { bg: '#1E293B', border: '#64748B', text: '#CBD5E1' },
            signal: { bg: '#713F12', border: '#FACC15', text: '#FDE68A' },
            urgent: { bg: '#7C2D12', border: '#F97316', text: '#FDBA74' },
        };
        const c = COLORS[bubble.type] || COLORS.wait;

        const pad = 5;
        ctx.font = 'bold 8px monospace';
        const tw = ctx.measureText(bubble.text).width;
        const bw = tw + pad * 2;
        const bh = 14;

        // Bubble rect
        ctx.fillStyle = c.bg;
        ctx.fillRect(bx - bw / 2, by - bh, bw, bh);
        ctx.strokeStyle = c.border;
        ctx.lineWidth = 1;
        ctx.strokeRect(bx - bw / 2, by - bh, bw, bh);

        // Tail triangle
        ctx.fillStyle = c.bg;
        ctx.beginPath();
        ctx.moveTo(bx - 4, by);
        ctx.lineTo(bx + 4, by);
        ctx.lineTo(bx, by + 5);
        ctx.fill();
        ctx.strokeStyle = c.border;
        ctx.beginPath();
        ctx.moveTo(bx - 4, by);
        ctx.lineTo(bx, by + 5);
        ctx.lineTo(bx + 4, by);
        ctx.stroke();

        // Text
        ctx.fillStyle = c.text;
        ctx.textAlign = 'center';
        ctx.fillText(bubble.text, bx, by - bh + 9);

        ctx.restore();
    }

    renderMatrixEffect(ctx, sprite, x, y, scale, ch) {
        // Render a basic pop-in for the moment - matrix effect detailed implementation 
        // will be added in Phase 9 Aesthetic Polish step.
        const progress = Math.min(ch.matrixEffectTimer / MATRIX_EFFECT_DURATION, 1.0);
        ctx.save();
        ctx.globalAlpha = progress; // Fade in

        // Apply the same sitting-behind-desk clipping during spawn
        ctx.beginPath();
        ctx.rect(x, y, sprite.width * scale, sprite.height * scale * 0.70);
        ctx.clip();

        ctx.drawImage(sprite, x, y, sprite.width * scale, sprite.height * scale);

        // Green scanner line
        ctx.fillStyle = '#00ff00';
        ctx.fillRect(x, y + (sprite.height * scale * progress), sprite.width * scale, 2);
        ctx.restore();
    }

    renderGrid(ctx, mapWidth, mapHeight) {
        // Render cyan debug grid overlay
        ctx.save();
        ctx.strokeStyle = 'rgba(0, 255, 255, 0.3)'; // Cyan alpha
        ctx.lineWidth = 1;
        ctx.font = '8px monospace';
        ctx.fillStyle = 'rgba(0, 255, 255, 0.7)';

        const cols = Math.floor(mapWidth / GRID_SIZE);
        const rows = Math.floor(mapHeight / GRID_SIZE);

        for (let x = 0; x <= cols; x++) {
            const worldX = x * GRID_SIZE;
            ctx.beginPath();
            ctx.moveTo(worldX, 0);
            ctx.lineTo(worldX, mapHeight);
            ctx.stroke();
            // Draw column index
            if (x < cols) {
                ctx.fillText(x.toString(), worldX + 2, 10);
            }
        }

        for (let y = 0; y <= rows; y++) {
            const worldY = y * GRID_SIZE;
            ctx.beginPath();
            ctx.moveTo(0, worldY);
            ctx.lineTo(mapWidth, worldY);
            ctx.stroke();
            // Draw row index
            if (y < rows) {
                ctx.fillText(y.toString(), 2, worldY + 10);
            }

            // Draw XY pair in every cell for calibration
            for (let x = 0; x < cols; x++) {
                ctx.fillText(`${x},${y}`, x * GRID_SIZE + 2, y * GRID_SIZE + GRID_SIZE - 2);
            }
        }
        ctx.restore();
    }
}
