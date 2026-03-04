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

        // 3. Collect & Z-Sort Drawables (Characters, specific furniture if needed)
        const drawables = [];

        for (const [id, ch] of officeState.characters.entries()) {
            const sprite = this.sprites[id];
            if (!sprite || !sprite.complete) continue;

            const scale = 2.0; // Increased to 2x per user request
            // X center. Y is shifted down 20px so they "sit" behind the desk correctly rather than floating on top
            const drawX = ch.x - (sprite.width * scale) / 2;
            const drawY = ch.y - (sprite.height * scale) + 20;
            const seat = officeState.seats.get(ch.seatId);

            // 3.5 Render Monitor Glow Native Effect (Underneath characters)
            if (seat && ch.isActive) {
                drawables.push({
                    zY: seat.my, // Glow renders right AT the monitor height
                    draw: (context) => {
                        context.save();
                        context.globalCompositeOperation = 'screen';
                        // Use agent state to determine glow color (green for normal, amber for warnings)
                        const isWarning = [CharacterState.URGENT, CharacterState.HOLD_ACTIVE, CharacterState.STAMPING_RED, CharacterState.KILL_TRIGGERED, CharacterState.STOPPED_OUT].includes(ch.state);
                        const colorHex = isWarning ? 'rgba(217, 119, 6, 0.4)' : 'rgba(16, 185, 129, 0.4)'; // Amber / Emerald

                        const gradient = context.createRadialGradient(seat.mx, seat.my, 5, seat.mx, seat.my, 40);
                        gradient.addColorStop(0, colorHex);
                        gradient.addColorStop(1, 'rgba(0,0,0,0)');

                        context.fillStyle = gradient;
                        context.fillRect(seat.mx - 40, seat.my - 40, 80, 80);
                        context.restore();
                    }
                });
            }

            // Push character into draw queue
            drawables.push({
                zY: ch.y + CHARACTER_Z_SORT_OFFSET,
                draw: (context) => {
                    // Handle Matrix Spawn Effect
                    if (ch.matrixEffect) {
                        this.renderMatrixEffect(context, sprite, drawX, drawY, scale, ch);
                    } else {
                        context.save();
                        // USER VISUAL PREFERENCE: Agents should appear "behind" the desks.
                        // Since the background map is a flat image, we simulate this by 
                        // clipping the bottom part of their sprite (the legs) so they sit *inside* the chair 
                        // and their body is cut off perfectly at the table line.
                        // We clip horizontally across the sprite width, from the top down to just above the feet.
                        context.beginPath();
                        // Adjust the clip height multiplier (0.65) to reveal more or less of the torso
                        context.rect(drawX, drawY, sprite.width * scale, sprite.height * scale * 0.70);
                        context.clip();

                        context.drawImage(sprite, drawX, drawY, sprite.width * scale, sprite.height * scale);
                        context.restore();
                    }
                }
            });
        }

        // Sort by depth (Y coordinate) for isometric 2D depth perception
        drawables.sort((a, b) => a.zY - b.zY);

        // Draw sorted characters/furniture over the background
        for (const d of drawables) {
            d.draw(ctx);
        }

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
