import { useEffect, useRef } from 'react';
import { routeEvent } from '../logic/EventAdapter';

export const useWebSocket = (url) => {
    const ws = useRef(null);
    const reconnectTimeout = useRef(null);

    const connect = () => {
        console.log(`[WS] Connecting to ${url}...`);
        ws.current = new WebSocket(url);

        ws.current.onopen = () => {
            console.log('[WS] Connected');
            if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
        };

        ws.current.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                routeEvent(data);
            } catch (err) {
                console.error('[WS] Failed to parse message', err);
            }
        };

        ws.current.onclose = () => {
            console.log('[WS] Disconnected, reconnecting in 3s...');
            reconnectTimeout.current = setTimeout(connect, 3000);
        };

        ws.current.onerror = (err) => {
            console.error('[WS] Error', err);
            ws.current.close();
        };
    };

    useEffect(() => {
        connect();
        return () => {
            if (ws.current) ws.current.close();
            if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
        };
    }, [url]);

    const send = (data) => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(data));
        }
    };

    return { send };
};
