import React, { useEffect, useRef, forwardRef } from 'react';

// A DPR-aware Canvas component specifically built for crisp pixel art.
// It sets backing store size using devicePixelRatio but CSS size logically.
export const OfficeCanvas = forwardRef(({ width, height, ...props }, ref) => {
    const canvasRef = useRef(null);

    // Forward the ref if provided
    useEffect(() => {
        if (ref) {
            if (typeof ref === 'function') ref(canvasRef.current);
            else ref.current = canvasRef.current;
        }
    }, [ref]);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        // Apply DPR scaling for sharp retina displays
        const dpr = window.devicePixelRatio || 1;

        // The actual backing store array of pixels
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);

        // The CSS size presented to the browser layout
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        const ctx = canvas.getContext('2d');
        if (ctx) {
            // Critical for pixel art - prevents edge blurring on scaling
            ctx.imageSmoothingEnabled = false;
        }
    }, [width, height]);

    return (
        <canvas
            ref={canvasRef}
            {...props}
            style={{
                ...props.style,
                imageRendering: 'pixelated' // CSS-level crispness
            }}
        />
    );
});

OfficeCanvas.displayName = 'OfficeCanvas';
