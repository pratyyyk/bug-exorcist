'use client';

import React from 'react';

interface ContextMapProps {
    referencedFiles: string[];
    isProcessing?: boolean;
}

export default function ContextMap({ referencedFiles, isProcessing = false }: ContextMapProps) {
    if (!isProcessing && referencedFiles.length === 0) {
        return null;
    }

    return (
        <div className="bg-black/40 border border-[#2a3a27] rounded-xl overflow-hidden backdrop-blur-sm p-4 h-full">
            <div className="flex items-center justify-between mb-4 border-b border-[#2a3a27] pb-2">
                <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[#38ff14] text-lg">map</span>
                    <h3 className="text-[#38ff14] text-[10px] font-bold uppercase tracking-widest font-display">
                        Knowledge Context Map
                    </h3>
                </div>
                {isProcessing && (
                    <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#38ff14] animate-pulse"></div>
                        <span className="text-[#38ff14]/60 text-[8px] uppercase tracking-tighter">Indexing...</span>
                    </div>
                )}
            </div>

            <div className="space-y-2 overflow-y-auto max-h-[calc(100%-3rem)] pr-2 terminal-scroll">
                {referencedFiles.length === 0 && isProcessing && (
                    <div className="flex flex-col items-center justify-center py-10 opacity-30">
                        <span className="material-symbols-outlined text-3xl animate-spin mb-2">sync</span>
                        <p className="text-[10px] uppercase tracking-widest text-center">Scanning Codebase...</p>
                    </div>
                )}

                {referencedFiles.length === 0 && !isProcessing && (
                    <div className="text-[#38ff14]/30 text-[10px] italic py-4 text-center">
                        No external files referenced yet.
                    </div>
                )}

                {referencedFiles.map((file, idx) => {
                    const extension = file.split('.').pop() || '';
                    const filename = file.split('/').pop() || file;
                    const path = file.split('/').slice(0, -1).join('/');

                    return (
                        <div 
                            key={idx} 
                            className="group p-2 rounded border border-[#38ff14]/10 bg-[#38ff14]/5 hover:border-[#38ff14]/40 hover:bg-[#38ff14]/10 transition-all cursor-default"
                        >
                            <div className="flex items-start gap-3">
                                <div className="mt-0.5 w-6 h-6 rounded flex items-center justify-center bg-black/40 border border-[#38ff14]/20 group-hover:border-[#38ff14]/50 transition-colors">
                                    <span className="text-[10px] font-bold text-[#38ff14]/70 uppercase">
                                        {extension.substring(0, 3)}
                                    </span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-[#38ff14] text-xs font-bold truncate">
                                        {filename}
                                    </p>
                                    <p className="text-[#38ff14]/40 text-[9px] font-mono truncate uppercase tracking-tighter">
                                        {path || 'ROOT'}
                                    </p>
                                </div>
                                <span className="material-symbols-outlined text-[#38ff14]/30 text-sm group-hover:text-[#38ff14]/80 transition-colors">
                                    visibility
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>
            
            <div className="mt-4 pt-2 border-t border-[#2a3a27]">
                <div className="flex items-center justify-between">
                    <span className="text-[#38ff14]/40 text-[9px] uppercase tracking-widest">Total References</span>
                    <span className="text-[#38ff14] text-xs font-bold font-mono">{referencedFiles.length}</span>
                </div>
            </div>
        </div>
    );
}
