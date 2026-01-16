'use client';

import React from 'react';

interface FallbackResponse {
  bug_id: string;
  status: string;
  fallback_enabled: boolean;
  total_attempts: number;
  timestamp: string;
  
  error_summary: {
    original_error: string;
    error_type: string;
    code_snippet: string;
  };
  
  ai_failure_notice?: {
    title: string;
    message: string;
    reason: string;
    impact: string;
  };
  
  service_notice?: {
    title: string;
    message: string;
    reason: string;
    impact: string;
  };
  
  manual_guidance?: {
    title: string;
    description: string;
    suggested_fixes: string[];
    example_solution: string;
  };
  
  debugging_steps?: Array<{
    step: number;
    action: string;
    description: string;
  }>;
  
  helpful_resources?: {
    documentation: Array<{
      name: string;
      url: string;
      description: string;
    }>;
    debugging_tools: Array<{
      name: string;
      description: string;
      usage: string;
    }>;
  };
  
  attempt_summary?: {
    attempts: Array<{
      attempt_number: number;
      result: string;
      error: string | null;
    }>;
    conclusion: string;
  };
  
  recommended_next_steps?: string[];
  
  troubleshooting?: {
    possible_causes: string[];
    solutions: string[];
  };
  
  manual_debugging?: {
    message: string;
    steps: string[];
  };
  
  recommended_actions?: string[];
}

interface FallbackDisplayProps {
  fallbackData: FallbackResponse;
  onRetry?: () => void;
  onClose?: () => void;
}

export default function FallbackDisplay({ fallbackData, onRetry, onClose }: FallbackDisplayProps) {
  const isApiFailure = fallbackData.status === 'api_connection_failed';
  const isAnalysisFailure = fallbackData.status === 'ai_analysis_failed';

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 p-6">
      {/* Header Section */}
      <div className="bg-gradient-to-r from-red-900/20 to-orange-900/20 border border-red-500/30 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-red-500/20 border border-red-500/50 flex items-center justify-center">
              <span className="material-symbols-outlined text-red-500 text-4xl">error</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-red-400 neon-glow tracking-widest uppercase">
                {isApiFailure ? 'AI Service Unavailable' : 'Automatic Fix Failed'}
              </h1>
              <p className="text-red-400/60 text-sm font-mono mt-1">
                Bug ID: {fallbackData.bug_id} • {fallbackData.total_attempts} attempts made
              </p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-red-500/10 rounded transition-colors"
            >
              <span className="material-symbols-outlined text-red-400">close</span>
            </button>
          )}
        </div>
        
        <div className="mt-4 p-4 bg-black/40 rounded-lg border border-red-500/20">
          <p className="text-[#38ff14]/80 font-mono text-sm leading-relaxed">
            {isApiFailure 
              ? fallbackData.service_notice?.message 
              : fallbackData.ai_failure_notice?.message}
          </p>
          <p className="text-[#38ff14]/60 text-xs mt-2">
            <strong>Reason:</strong>{' '}
            {isApiFailure 
              ? fallbackData.service_notice?.reason 
              : fallbackData.ai_failure_notice?.reason}
          </p>
        </div>
      </div>

      {/* Error Summary */}
      <div className="bg-black/40 border border-[#2a3a27] rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center gap-3 mb-4">
          <span className="material-symbols-outlined text-[#38ff14]">bug_report</span>
          <h2 className="text-lg font-bold text-[#38ff14] uppercase tracking-widest">Error Summary</h2>
        </div>
        
        <div className="space-y-3">
          <div>
            <p className="text-[#38ff14]/60 text-xs uppercase font-bold mb-1">Error Type</p>
            <p className="text-[#38ff14] font-mono bg-black/40 px-3 py-2 rounded border border-[#2a3a27]">
              {fallbackData.error_summary.error_type}
            </p>
          </div>
          
          <div>
            <p className="text-[#38ff14]/60 text-xs uppercase font-bold mb-1">Original Error</p>
            <pre className="text-[#38ff14] font-mono text-xs bg-black/40 px-3 py-2 rounded border border-[#2a3a27] overflow-x-auto">
              {fallbackData.error_summary.original_error}
            </pre>
          </div>
          
          <div>
            <p className="text-[#38ff14]/60 text-xs uppercase font-bold mb-1">Code Snippet</p>
            <pre className="text-[#38ff14] font-mono text-xs bg-black/40 px-3 py-2 rounded border border-[#2a3a27] overflow-x-auto">
              {fallbackData.error_summary.code_snippet}
            </pre>
          </div>
        </div>
      </div>

      {/* Attempt Summary (if available) */}
      {fallbackData.attempt_summary && (
        <div className="bg-black/40 border border-[#2a3a27] rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-yellow-500">history</span>
            <h2 className="text-lg font-bold text-[#38ff14] uppercase tracking-widest">Attempt History</h2>
          </div>
          
          <div className="space-y-2 mb-4">
            {fallbackData.attempt_summary.attempts.map((attempt) => (
              <div key={attempt.attempt_number} className="flex items-center gap-3 p-3 bg-black/40 rounded border border-[#2a3a27]">
                <span className={`material-symbols-outlined ${attempt.result === 'PASSED' ? 'text-green-500' : 'text-red-500'}`}>
                  {attempt.result === 'PASSED' ? 'check_circle' : 'cancel'}
                </span>
                <div className="flex-1">
                  <p className="text-[#38ff14] font-mono text-sm">Attempt {attempt.attempt_number}: {attempt.result}</p>
                  {attempt.error && (
                    <p className="text-[#38ff14]/60 text-xs font-mono mt-1">{attempt.error}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
          
          <p className="text-[#38ff14]/80 text-sm font-mono italic">
            {fallbackData.attempt_summary.conclusion}
          </p>
        </div>
      )}

      {/* Manual Guidance (if available) */}
      {fallbackData.manual_guidance && (
        <div className="bg-gradient-to-br from-[#38ff14]/5 to-blue-500/5 border border-[#38ff14]/30 rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-[#38ff14]">lightbulb</span>
            <h2 className="text-lg font-bold text-[#38ff14] uppercase tracking-widest">
              {fallbackData.manual_guidance.title}
            </h2>
          </div>
          
          <p className="text-[#38ff14]/80 mb-4 leading-relaxed">
            {fallbackData.manual_guidance.description}
          </p>
          
          <div className="mb-4">
            <p className="text-[#38ff14] font-bold text-sm uppercase mb-2">Suggested Fixes:</p>
            <ul className="space-y-2">
              {fallbackData.manual_guidance.suggested_fixes.map((fix, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-[#38ff14] text-sm mt-0.5">arrow_forward</span>
                  <span className="text-[#38ff14]/80 text-sm">{fix}</span>
                </li>
              ))}
            </ul>
          </div>
          
          <div>
            <p className="text-[#38ff14] font-bold text-sm uppercase mb-2">Example Solution:</p>
            <pre className="text-[#38ff14] font-mono text-xs bg-black/60 px-4 py-3 rounded border border-[#38ff14]/30 overflow-x-auto">
              {fallbackData.manual_guidance.example_solution}
            </pre>
          </div>
        </div>
      )}

      {/* Troubleshooting (for API failures) */}
      {fallbackData.troubleshooting && (
        <div className="bg-black/40 border border-[#2a3a27] rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-yellow-500">build</span>
            <h2 className="text-lg font-bold text-[#38ff14] uppercase tracking-widest">Troubleshooting</h2>
          </div>
          
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <p className="text-[#38ff14] font-bold text-sm uppercase mb-2">Possible Causes:</p>
              <ul className="space-y-1">
                {fallbackData.troubleshooting.possible_causes.map((cause, idx) => (
                  <li key={idx} className="text-[#38ff14]/70 text-sm flex items-start gap-2">
                    <span className="text-red-500 mt-0.5">•</span>
                    {cause}
                  </li>
                ))}
              </ul>
            </div>
            
            <div>
              <p className="text-[#38ff14] font-bold text-sm uppercase mb-2">Solutions:</p>
              <ul className="space-y-1">
                {fallbackData.troubleshooting.solutions.map((solution, idx) => (
                  <li key={idx} className="text-[#38ff14]/70 text-sm flex items-start gap-2">
                    <span className="text-green-500 mt-0.5">✓</span>
                    {solution}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Debugging Steps */}
      {fallbackData.debugging_steps && (
        <div className="bg-black/40 border border-[#2a3a27] rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-[#38ff14]">troubleshoot</span>
            <h2 className="text-lg font-bold text-[#38ff14] uppercase tracking-widest">Debugging Steps</h2>
          </div>
          
          <div className="space-y-3">
            {fallbackData.debugging_steps.map((step) => (
              <div key={step.step} className="flex gap-4 p-4 bg-black/40 rounded border border-[#2a3a27] hover:border-[#38ff14]/30 transition-colors">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#38ff14]/20 border border-[#38ff14]/50 flex items-center justify-center">
                  <span className="text-[#38ff14] font-bold text-sm">{step.step}</span>
                </div>
                <div className="flex-1">
                  <p className="text-[#38ff14] font-bold text-sm uppercase mb-1">{step.action}</p>
                  <p className="text-[#38ff14]/70 text-sm">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Helpful Resources */}
      {fallbackData.helpful_resources && (
        <div className="bg-black/40 border border-[#2a3a27] rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-[#38ff14]">school</span>
            <h2 className="text-lg font-bold text-[#38ff14] uppercase tracking-widest">Helpful Resources</h2>
          </div>
          
          <div className="grid md:grid-cols-2 gap-6">
            {/* Documentation Links */}
            {fallbackData.helpful_resources.documentation && (
              <div>
                <p className="text-[#38ff14] font-bold text-sm uppercase mb-3">Documentation</p>
                <div className="space-y-2">
                  {fallbackData.helpful_resources.documentation.map((doc, idx) => (
                    <a
                      key={idx}
                      href={doc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block p-3 bg-black/40 rounded border border-[#2a3a27] hover:border-[#38ff14]/50 transition-colors group"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="material-symbols-outlined text-[#38ff14] text-sm">link</span>
                        <p className="text-[#38ff14] font-mono text-sm group-hover:neon-glow">{doc.name}</p>
                      </div>
                      <p className="text-[#38ff14]/60 text-xs">{doc.description}</p>
                    </a>
                  ))}
                </div>
              </div>
            )}
            
            {/* Debugging Tools */}
            {fallbackData.helpful_resources.debugging_tools && (
              <div>
                <p className="text-[#38ff14] font-bold text-sm uppercase mb-3">Debugging Tools</p>
                <div className="space-y-2">
                  {fallbackData.helpful_resources.debugging_tools.map((tool, idx) => (
                    <div key={idx} className="p-3 bg-black/40 rounded border border-[#2a3a27]">
                      <p className="text-[#38ff14] font-mono text-sm mb-1">{tool.name}</p>
                      <p className="text-[#38ff14]/60 text-xs mb-2">{tool.description}</p>
                      <code className="text-[#38ff14] text-xs bg-black/60 px-2 py-1 rounded">
                        {tool.usage}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recommended Next Steps */}
      {(fallbackData.recommended_next_steps || fallbackData.recommended_actions) && (
        <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 border border-blue-500/30 rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-blue-400">directions</span>
            <h2 className="text-lg font-bold text-[#38ff14] uppercase tracking-widest">Recommended Next Steps</h2>
          </div>
          
          <ul className="space-y-2">
            {(fallbackData.recommended_next_steps || fallbackData.recommended_actions || []).map((step, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <span className="material-symbols-outlined text-blue-400 text-sm mt-0.5">check</span>
                <span className="text-[#38ff14]/80 text-sm">{step}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-4 justify-end pt-4">
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-6 py-3 bg-[#38ff14]/10 border border-[#38ff14]/50 text-[#38ff14] rounded-lg hover:bg-[#38ff14]/20 transition-all font-bold text-sm tracking-widest uppercase group flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-xl group-hover:neon-glow">refresh</span>
            Retry Analysis
          </button>
        )}
        
        <a
          href="https://docs.anthropic.com"
          target="_blank"
          rel="noopener noreferrer"
          className="px-6 py-3 bg-blue-500/10 border border-blue-500/50 text-blue-400 rounded-lg hover:bg-blue-500/20 transition-all font-bold text-sm tracking-widest uppercase group flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-xl">help</span>
          Get Help
        </a>
      </div>
    </div>
  );
}