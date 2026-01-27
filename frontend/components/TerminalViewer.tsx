'use client';

import React, { useEffect, useRef, useState } from 'react';

interface ThoughtEvent {
    type: 'thought' | 'status' | 'result' | 'error';
    timestamp: string;
    message: string;
    stage: string;
    data?: any;
}

interface TerminalViewerProps {
    sessionId: string;
    onAnalysisRequest?: () => {
        error_message: string;
        code_snippet: string;
        file_path?: string;
        additional_context?: string;
        use_retry?: boolean;
        max_attempts?: number;
    };
    autoConnect?: boolean;
}

export default function TerminalViewer({
    sessionId,
    onAnalysisRequest,
    autoConnect = false
}: TerminalViewerProps) {
    const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
    const scrollRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

    // Auto-scroll to bottom when new thoughts arrive
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [thoughts]);

    // WebSocket connection management
    const connectWebSocket = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return; // Already connected
        }

        setConnectionStatus('connecting');
        addThought({
            type: 'status',
            timestamp: new Date().toISOString(),
            message: `Connecting to thought stream...`,
            stage: 'initialization'
        });

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
        const ws = new WebSocket(`${protocol}//${host}/ws/thought-stream/${sessionId}`);

        ws.onopen = () => {
            setIsConnected(true);
            setConnectionStatus('connected');
            addThought({
                type: 'status',
                timestamp: new Date().toISOString(),
                message: '✅ Connected to AI thought stream',
                stage: 'initialization'
            });

            // If we have an analysis request, send it immediately
            if (onAnalysisRequest) {
                const request = onAnalysisRequest();
                ws.send(JSON.stringify({
                    action: 'analyze',
                    ...request
                }));
                setIsProcessing(true);
            }
        };

        ws.onmessage = (event) => {
            try {
                const thoughtEvent: ThoughtEvent = JSON.parse(event.data);
                addThought(thoughtEvent);

                // Check if processing is complete
                if (thoughtEvent.type === 'result' || thoughtEvent.type === 'error') {
                    setIsProcessing(false);
                }
            } catch (error) {
                console.error('Failed to parse thought event:', error);
            }
        };

        ws.onerror = (error) => {
            setConnectionStatus('error');
            addThought({
                type: 'error',
                timestamp: new Date().toISOString(),
                message: '❌ WebSocket connection error',
                stage: 'error'
            });
        };

        ws.onclose = (event) => {
            setIsConnected(false);
            setConnectionStatus('disconnected');
            setIsProcessing(false);

            if (!event.wasClean) {
                addThought({
                    type: 'status',
                    timestamp: new Date().toISOString(),
                    message: '🔌 Disconnected from thought stream',
                    stage: 'disconnected'
                });

                // Attempt to reconnect after 3 seconds
                reconnectTimeoutRef.current = setTimeout(() => {
                    addThought({
                        type: 'status',
                        timestamp: new Date().toISOString(),
                        message: '🔄 Attempting to reconnect...',
                        stage: 'reconnecting'
                    });
                    connectWebSocket();
                }, 3000);
            }
        };

        wsRef.current = ws;
    };

    const addThought = (thought: ThoughtEvent) => {
        setThoughts(prev => [...prev, thought]);
    };

    const disconnectWebSocket = () => {
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
        }
    };

    useEffect(() => {
        if (autoConnect) {
            connectWebSocket();
        }

        return () => {
            disconnectWebSocket();
        };
    }, [sessionId, autoConnect]);

    const getThoughtIcon = (thought: ThoughtEvent) => {
        switch (thought.type) {
            case 'status':
                return '🔵';
            case 'thought':
                if (thought.message.includes('✅')) return '✅';
                if (thought.message.includes('❌')) return '❌';
                if (thought.message.includes('🤖')) return '🤖';
                if (thought.message.includes('🧪')) return '🧪';
                return '💭';
            case 'result':
                return thought.data?.success ? '🎉' : '⚠️';
            case 'error':
                return '🔴';
            default:
                return '•';
        }
    };

    const getThoughtColor = (thought: ThoughtEvent) => {
        switch (thought.type) {
            case 'status':
                return 'text-blue-400';
            case 'thought':
                if (thought.message.includes('✅')) return 'text-green-400';
                if (thought.message.includes('❌')) return 'text-red-400';
                return 'text-[#38ff14]';
            case 'result':
                return thought.data?.success ? 'text-green-400' : 'text-yellow-400';
            case 'error':
                return 'text-red-400';
            default:
                return 'text-[#38ff14]/70';
        }
    };

    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    const clearThoughts = () => {
        setThoughts([]);
    };

    return (
        <div className="flex flex-col bg-black/40 border border-[#2a3a27] rounded-xl overflow-hidden backdrop-blur-sm h-[calc(100vh-12rem)]">
            {/* Terminal Header */}
            <div className="h-12 border-b border-[#2a3a27] bg-black/60 flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-[#38ff14]/70 text-lg">psychology</span>
                    <h2 className="text-[#38ff14] text-xs font-bold tracking-widest uppercase neon-glow font-display">
                        AI Thought Stream
                    </h2>
                    <div className="flex items-center gap-2 ml-4">
                        {connectionStatus === 'connected' && (
                            <>
                                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_#22c55e]"></div>
                                <span className="text-green-400 text-[10px] uppercase tracking-wider">Live</span>
                            </>
                        )}
                        {connectionStatus === 'connecting' && (
                            <>
                                <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse"></div>
                                <span className="text-yellow-400 text-[10px] uppercase tracking-wider">Connecting...</span>
                            </>
                        )}
                        {connectionStatus === 'disconnected' && (
                            <>
                                <div className="w-2 h-2 rounded-full bg-gray-500"></div>
                                <span className="text-gray-400 text-[10px] uppercase tracking-wider">Disconnected</span>
                            </>
                        )}
                        {connectionStatus === 'error' && (
                            <>
                                <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                                <span className="text-red-400 text-[10px] uppercase tracking-wider">Error</span>
                            </>
                        )}
                    </div>
                </div>
                <div className="flex gap-2">
                    {!isConnected && (
                        <button
                            onClick={connectWebSocket}
                            className="px-3 py-1 text-[10px] border border-[#38ff14]/30 rounded hover:bg-[#38ff14]/10 transition-all uppercase tracking-widest text-[#38ff14]/70 hover:text-[#38ff14]"
                        >
                            Connect
                        </button>
                    )}
                    {isConnected && (
                        <button
                            onClick={disconnectWebSocket}
                            className="px-3 py-1 text-[10px] border border-red-500/30 rounded hover:bg-red-500/10 transition-all uppercase tracking-widest text-red-400/70 hover:text-red-400"
                        >
                            Disconnect
                        </button>
                    )}
                    <button
                        onClick={clearThoughts}
                        className="px-3 py-1 text-[10px] border border-[#2a3a27] rounded hover:bg-[#38ff14]/5 transition-all uppercase tracking-widest text-[#38ff14]/50 hover:text-[#38ff14]/70"
                    >
                        Clear
                    </button>
                    <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500/50"></div>
                    </div>
                </div>
            </div>

            {/* Terminal Content Area */}
            <div className="flex-1 overflow-y-auto p-4 font-mono terminal-scroll" ref={scrollRef}>
                {thoughts.length === 0 && !isConnected && (
                    <div className="flex flex-col items-center justify-center h-full text-[#38ff14]/30">
                        <span className="material-symbols-outlined text-6xl mb-4">power_off</span>
                        <p className="text-sm uppercase tracking-widest">Thought stream not connected</p>
                        <p className="text-[10px] mt-2">Click "Connect" to start streaming</p>
                    </div>
                )}

                {thoughts.length === 0 && isConnected && (
                    <div className="flex flex-col items-center justify-center h-full text-[#38ff14]/30">
                        <span className="material-symbols-outlined text-6xl mb-4 animate-pulse">hourglass_empty</span>
                        <p className="text-sm uppercase tracking-widest">Waiting for thoughts...</p>
                    </div>
                )}

                <div className="space-y-1">
                    {thoughts.map((thought, index) => (
                        <div
                            key={index}
                            className="flex gap-3 group hover:bg-[#38ff14]/5 pl-2 -ml-2 pr-2 rounded transition-colors py-1 animate-[fadeIn_0.3s_ease-in]"
                        >
                            <span className="text-[#38ff14]/40 text-[10px] font-mono shrink-0 w-16">
                                [{formatTimestamp(thought.timestamp)}]
                            </span>
                            <span className="text-lg shrink-0">
                                {getThoughtIcon(thought)}
                            </span>
                            <div className="flex-1 min-w-0">
                                <p className={`${getThoughtColor(thought)} break-words text-sm leading-relaxed`}>
                                    {thought.message}
                                </p>
                                {thought.data && Object.keys(thought.data).length > 0 && (
                                    <details className="mt-1 text-[#38ff14]/50 text-[10px]">
                                        <summary className="cursor-pointer hover:text-[#38ff14]/70 uppercase tracking-wider">
                                            View Details
                                        </summary>
                                        <pre className="mt-2 p-2 bg-black/40 rounded border border-[#2a3a27] overflow-x-auto text-[#38ff14]/70">
                                            {JSON.stringify(thought.data, null, 2)}
                                        </pre>
                                    </details>
                                )}
                            </div>
                        </div>
                    ))}

                    {isProcessing && (
                        <div className="flex items-center gap-3 pl-2 py-2">
                            <span className="text-[#38ff14]/40 text-[10px] font-mono w-16">
                                [--:--:--]
                            </span>
                            <div className="flex gap-1">
                                <span className="w-2 h-2 rounded-full bg-[#38ff14] animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                <span className="w-2 h-2 rounded-full bg-[#38ff14] animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                <span className="w-2 h-2 rounded-full bg-[#38ff14] animate-bounce" style={{ animationDelay: '300ms' }}></span>
                            </div>
                            <span className="text-[#38ff14]/60 text-sm">Thinking...</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Terminal Footer */}
            <div className="h-8 border-t border-[#2a3a27] bg-black/60 flex items-center justify-between px-4 text-[10px] font-mono shrink-0">
                <div className="flex gap-4 text-[#38ff14]/40 uppercase tracking-widest">
                    <span>Session: {sessionId.slice(0, 8)}</span>
                    <span>Thoughts: {thoughts.length}</span>
                </div>
                <div className="flex gap-4 items-center">
                    {isProcessing && (
                        <div className="flex items-center gap-1 text-[#38ff14]/60">
                            <span className="material-symbols-outlined text-sm animate-spin">autorenew</span>
                            <span>PROCESSING</span>
                        </div>
                    )}
                    {isConnected && !isProcessing && (
                        <div className="flex items-center gap-1 text-[#38ff14]/60">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#38ff14] animate-pulse shadow-[0_0_8px_#38ff14]"></span>
                            <span>READY</span>
                        </div>
                    )}
                </div>
            </div>

            <style jsx>{`
                @keyframes fadeIn {
                    from {
                        opacity: 0;
                        transform: translateY(-10px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
            `}</style>
        </div>
    );
}