// Pure HTML5 Canvas Game Loop (Pure JS, no TypeScript)
// Pattern adopted from pixel-agents engine

const MAX_DELTA_TIME_SEC = 0.1;

export function startGameLoop(canvas, callbacks) {
    let rafId;
    let lastTime = performance.now();
    let stopped = false;

    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Failed to get 2D context');

    const frame = (time) => {
        if (stopped) return;

        // Use seconds for dt, capped to prevent massive jumps on tab switch
        const dt = Math.min((time - lastTime) / 1000, MAX_DELTA_TIME_SEC);
        lastTime = time;

        callbacks.update(dt);

        // Critical for crisp pixel art - no bilinear blurring
        ctx.imageSmoothingEnabled = false;

        callbacks.render(ctx);

        rafId = requestAnimationFrame(frame);
    };

    rafId = requestAnimationFrame(frame);

    // Return a cleanup function to cancel the loop
    return () => {
        stopped = true;
        cancelAnimationFrame(rafId);
    };
}
