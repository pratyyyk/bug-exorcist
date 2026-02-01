"use client";

import { useState, useEffect } from "react";
import TerminalViewer from "../components/TerminalViewer";

export default function Home() {
    const [sessionId, setSessionId] = useState<string>("");

    useEffect(() => {
        // Generate a secure session ID for the demo
        const secureId = typeof crypto !== 'undefined' && crypto.randomUUID 
            ? `sess-${crypto.randomUUID()}` 
            : `sess-${Math.random().toString(36).substring(2, 15)}-${Date.now().toString(36)}`;
        setSessionId(secureId);
    }, []);

    return (
        <div className="space-y-6">
            {/* Dashboard Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                    { label: 'Bugs Detected', value: '42', icon: 'bug_report', color: 'text-red-500' },
                    { label: 'Fixed Today', value: '12', icon: 'check_circle', color: 'text-green-500' },
                    { label: 'Active Sessions', value: '3', icon: 'bolt', color: 'text-yellow-500' },
                    { label: 'System Health', value: '98%', icon: 'security', color: 'text-blue-500' },
                ].map((stat, idx) => (
                    <div key={idx} className="p-4 rounded-xl border border-[#2a3a27] bg-black/40 backdrop-blur-sm group hover:border-[#38ff14]/30 transition-all">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[#38ff14]/40 text-[10px] font-bold uppercase tracking-widest">{stat.label}</span>
                            <span className={`material-symbols-outlined ${stat.color} text-lg group-hover:scale-110 transition-transform`}>{stat.icon}</span>
                        </div>
                        <div className="flex items-end gap-2">
                            <span className="text-2xl font-bold text-[#38ff14] neon-glow">{stat.value}</span>
                            <div className="mb-1 h-1 w-full bg-[#38ff14]/10 rounded-full overflow-hidden">
                                <div className="h-full bg-[#38ff14] w-[65%] shadow-[0_0_5px_#38ff14]"></div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Terminal Viewer */}
            {sessionId && <TerminalViewer sessionId={sessionId} />}
        </div>
    );
}
