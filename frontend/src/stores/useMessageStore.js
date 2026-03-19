import { create } from 'zustand';

/**
 * useMessageStore manages the real-time communication pipeline between agents.
 * It tracks who said what to whom, allowing users to trace the decision-making process.
 */
export const useMessageStore = create((set) => ({
    messages: [],
    unreadCount: 0,
    isDrawerOpen: false,

    /**
     * Add a new message to the pipeline
     * @param {Object} message - { id, senderId, receiverId, content, type, timestamp }
     */
    addMessage: (message) => set((state) => ({
        messages: [
            {
                ...message,
                id: message.id || Date.now(),
                timestamp: message.timestamp || new Date().toISOString(),
            },
            ...state.messages
        ].slice(0, 100), // Keep last 100 messages
        unreadCount: state.isDrawerOpen ? 0 : state.unreadCount + 1
    })),

    setDrawerOpen: (isOpen) => set({
        isDrawerOpen: isOpen,
        unreadCount: isOpen ? 0 : undefined // Reset unread when opening
    }),

    clearMessages: () => set({ messages: [], unreadCount: 0 }),
}));
