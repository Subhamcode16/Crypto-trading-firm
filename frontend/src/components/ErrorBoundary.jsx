import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('React Error Boundary caught an error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    position: 'fixed', inset: 0, background: '#011301', color: '#00ff00',
                    fontFamily: 'monospace', padding: '24px', whiteSpace: 'pre-wrap', overflowY: 'auto',
                    fontSize: '12px', zIndex: 9999
                }}>
                    <h2 style={{ color: '#ff4444', marginBottom: '16px' }}>⚠ PIXEL FIRM - RUNTIME ERROR</h2>
                    <p>{this.state.error?.toString()}</p>
                    <p style={{ color: '#888', marginTop: '12px' }}>{this.state.error?.stack}</p>
                </div>
            );
        }
        return this.props.children;
    }
}

export default ErrorBoundary;
