'use client';

import React, { useEffect, useRef } from 'react';

interface TerminalViewerProps {
    logs?: string[];
    bugId?: string;
}

export default function TerminalViewer({ logs: initialLogs = [], bugId }: TerminalViewerProps) {
    const [logs, setLogs] = React.useState<string[]>(initialLogs);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when logs change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    // WebSocket connection
    useEffect(() => {
        if (!bugId) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
        const ws = new WebSocket(`${protocol}//${host}/ws/logs/${bugId}`);

        ws.onopen = () => {
            setLogs(prev => [...prev, `[SYSTEM] Connected to log stream for bug: ${bugId}`]);
        };

        ws.onmessage = (event) => {
            setLogs(prev => [...prev, event.data]);
        };

        ws.onerror = (error) => {
            setLogs(prev => [...prev, `[ERROR] WebSocket error: ${error}`]);
        };

        ws.onclose = () => {
            setLogs(prev => [...prev, `[SYSTEM] Disconnected from log stream`]);
        };

        return () => {
            ws.close();
        };
    }, [bugId]);

    // Default demo logs if none provided and no bugId
    const demoLogs = [
        "[22:04:11] SYSTEM :: Booting kernel version 4.1.2-PRIME...",
        "[22:04:11] SYSTEM :: Initializing hardware abstraction layer...",
        "[22:04:12] AUTH :: Login success. Welcome back, ROOT_USER.",
        "[22:04:12] UPLINK :: Scanning for available bridge nodes...",
        "[22:04:13] UPLINK :: Found Node-74 (Beijing), Node-12 (Amsterdam), Node-01 (San Francisco).",
        "[22:04:14] UPLINK :: Connecting to Node-01...",
        "[22:04:15] UPLINK :: ESTABLISHED. ENCRYPTION AES-256 ACTIVE.",
        "[22:05:01] PROCESS :: Running decryption script 'hydra_v4.sh'",
        "[22:05:01] DECRYPTING PACKETS... 74% - CRC Checksum Pending..."
    ];

    const currentLogs = logs.length > 0 ? logs : (!bugId ? demoLogs : []);

    return (
        <div className="flex flex-col bg-black/40 border border-[#2a3a27] rounded-xl overflow-hidden backdrop-blur-sm h-[calc(100vh-12rem)]">
            {/* Terminal Header */}
            <div className="h-10 border-b border-[#2a3a27] bg-black/60 flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[#38ff14]/70 text-lg">terminal</span>
                    <h2 className="text-[#38ff14] text-xs font-bold tracking-widest uppercase neon-glow font-display">Console Output</h2>
                </div>
                <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-green-500/50"></div>
                </div>
            </div>

            {/* Terminal Area */}
            <div className="flex-1 overflow-y-auto p-6 font-mono terminal-scroll" ref={scrollRef}>
                <div className="space-y-1">
                    {currentLogs.map((log, index) => (
                        <div key={index} className="flex gap-4 group hover:bg-[#38ff14]/5 pl-2 -ml-2 rounded transition-colors">
                            <p className="text-[#38ff14]/80 break-words w-full text-sm leading-relaxed">{log}</p>
                        </div>
                    ))}

                    {/* Input Line */}
                    <div className="py-2"></div>
                    <div className="flex gap-2 items-center">
                        <span className="text-[#38ff14] font-bold text-sm">root@terminal:~$</span>
                        <span className="text-[#38ff14] neon-glow text-sm">./init_payload --force</span>
                        <span className="cursor block w-2 h-4 bg-[#38ff14]"></span>
                    </div>
                </div>
            </div>

            {/* Terminal Footer */}
            <div className="h-8 border-t border-[#2a3a27] bg-black/60 flex items-center justify-between px-4 text-[10px] font-mono shrink-0">
                <div className="flex gap-4 text-[#38ff14]/40 uppercase tracking-widest">
                    <span>Session: 0x821</span>
                    <span>Buffer: 1024KB</span>
                </div>
                <div className="flex gap-4 items-center">
                    <div className="flex items-center gap-1 text-[#38ff14]/60">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#38ff14] animate-pulse"></span>
                        <span>LOGGING ACTIVE</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
