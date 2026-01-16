"use client";

import { useEffect, useState } from "react";

export default function SettingsPage() {
  const [mounted, setMounted] = useState(false);
  const [githubRepo, setGithubRepo] = useState("");
  const [apiStatus, setApiStatus] = useState<{
    checking: boolean;
    connected: boolean;
    model?: string;
    error?: string;
  }>({ checking: true, connected: false });

  useEffect(() => {
    setMounted(true);
    setGithubRepo(localStorage.getItem("github_repo_url") || "");
    checkApiConnection();
  }, []);

  const checkApiConnection = async () => {
    setApiStatus({ checking: true, connected: false });
    
    try {
      const response = await fetch("http://localhost:8000/api/agent/health");
      const data = await response.json();
      
      if (data.api_key_configured) {
        setApiStatus({
          checking: false,
          connected: true,
          model: data.model || "gpt-4o"
        });
      } else {
        setApiStatus({
          checking: false,
          connected: false,
          error: "API key not configured in .env file"
        });
      }
    } catch (error) {
      setApiStatus({
        checking: false,
        connected: false,
        error: "Cannot connect to backend server"
      });
    }
  };

  const saveSettings = () => {
    if (!githubRepo.trim()) {
      alert("Please fill in the GitHub Repository URL.");
      return;
    }
    localStorage.setItem("github_repo_url", githubRepo);
    alert("Settings saved successfully!");
  };

  if (!mounted) {
    return null;
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[#38ff14] neon-glow tracking-widest uppercase mb-2">Configuration</h1>
        <p className="text-[#38ff14]/60 text-sm font-mono italic">Adjust system parameters for optimal bug exorcism.</p>
      </div>

      <div className="space-y-6">
        {/* OpenAI API Status Display */}
        <div className={`p-6 rounded-xl border backdrop-blur-sm space-y-4 ${
          apiStatus.connected 
            ? 'border-[#38ff14]/50 bg-[#38ff14]/5' 
            : 'border-red-500/50 bg-red-900/5'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className={`material-symbols-outlined ${
                apiStatus.connected ? 'text-[#38ff14]' : 'text-red-500'
              }`}>
                {apiStatus.checking ? 'sync' : apiStatus.connected ? 'check_circle' : 'error'}
              </span>
              <label className={`text-xs font-bold uppercase tracking-widest ${
                apiStatus.connected ? 'text-[#38ff14]' : 'text-red-500'
              }`}>
                OpenAI GPT-4o Status
              </label>
            </div>
            
            <button
              onClick={checkApiConnection}
              className="px-3 py-1 text-[10px] border border-[#38ff14]/30 rounded hover:bg-[#38ff14]/10 transition-all uppercase tracking-widest text-[#38ff14]/70 hover:text-[#38ff14]"
              disabled={apiStatus.checking}
            >
              {apiStatus.checking ? 'Checking...' : 'Refresh'}
            </button>
          </div>

          {/* Status Display */}
          <div className="flex items-center gap-4 p-4 rounded-lg bg-black/40 border border-[#2a3a27]">
            {apiStatus.checking ? (
              <div className="flex items-center gap-3 text-[#38ff14]/60">
                <span className="material-symbols-outlined animate-spin">autorenew</span>
                <span className="text-sm font-mono">Checking connection...</span>
              </div>
            ) : apiStatus.connected ? (
              <>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-[#38ff14] animate-pulse shadow-[0_0_8px_#38ff14]"></div>
                  <span className="text-[#38ff14] font-bold text-sm uppercase tracking-wider">Active</span>
                </div>
                <div className="h-4 w-px bg-[#38ff14]/30"></div>
                <div className="text-[#38ff14]/80 text-sm font-mono">
                  Model: <span className="text-[#38ff14] font-bold">{apiStatus.model}</span>
                </div>
                <div className="ml-auto flex items-center gap-2 px-3 py-1 bg-[#38ff14]/10 rounded border border-[#38ff14]/30">
                  <span className="material-symbols-outlined text-[#38ff14] text-sm">neurology</span>
                  <span className="text-[10px] uppercase tracking-widest text-[#38ff14]">AI Ready</span>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-3 text-red-500/80">
                <span className="material-symbols-outlined">error</span>
                <div className="flex-1">
                  <p className="text-sm font-mono">{apiStatus.error}</p>
                  <p className="text-[10px] mt-1 text-red-500/60 uppercase">Configure OPENAI_API_KEY in backend/.env file</p>
                </div>
              </div>
            )}
          </div>

          <p className="text-[#38ff14]/40 text-[10px] uppercase leading-relaxed">
            The AI agent uses GPT-4o to analyze bugs and generate fixes. API key is securely stored in the backend .env file.
          </p>
        </div>

        {/* GitHub Repository */}
        <div className="p-6 rounded-xl border border-[#2a3a27] bg-black/40 backdrop-blur-sm space-y-4">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[#38ff14]">source</span>
            <label className="text-[#38ff14] text-xs font-bold uppercase tracking-widest">GitHub Repository URL</label>
          </div>
          <input
            type="text"
            value={githubRepo}
            onChange={(e) => setGithubRepo(e.target.value)}
            placeholder="https://github.com/user/repo"
            className="w-full bg-black/60 border border-[#2a3a27] rounded-lg px-4 py-3 text-[#38ff14] font-mono text-sm focus:outline-none focus:border-[#38ff14]/50 transition-colors placeholder:text-[#38ff14]/20"
          />
          <p className="text-[#38ff14]/40 text-[10px] uppercase leading-relaxed">
            The target codebase where bugs will be hunted and eliminated.
          </p>
        </div>

        {/* Save Button */}
        <div className="flex justify-end pt-4">
          <button 
            onClick={saveSettings}
            className="flex items-center gap-2 px-8 py-3 bg-[#38ff14]/10 border border-[#38ff14]/50 text-[#38ff14] rounded-lg hover:bg-[#38ff14]/20 transition-all font-bold text-sm tracking-widest uppercase group"
          >
            <span className="material-symbols-outlined text-xl group-hover:neon-glow transition-all">save</span>
            Save Configuration
          </button>
        </div>
      </div>

      {/* System Info */}
      <div className="pt-10 border-t border-[#2a3a27]/50 space-y-4">
        {/* AI Capabilities */}
        <div className="p-4 rounded-lg border border-[#38ff14]/20 bg-[#38ff14]/5">
          <div className="flex items-center gap-2 mb-3">
            <span className="material-symbols-outlined text-[#38ff14] text-sm">psychology</span>
            <p className="text-[#38ff14] text-[10px] font-bold uppercase tracking-widest">AI Capabilities</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              'Error Analysis',
              'Code Generation', 
              'Root Cause Detection',
              'Automated Testing'
            ].map((capability, idx) => (
              <div key={idx} className="flex items-center gap-2 text-[#38ff14]/60 text-[10px]">
                <span className="material-symbols-outlined text-xs">check</span>
                <span>{capability}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Security Notice */}
        <div className="p-4 rounded-lg border border-red-900/30 bg-red-900/5">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-symbols-outlined text-red-500 text-sm">warning</span>
            <p className="text-red-500 text-[10px] font-bold uppercase tracking-widest">Security Protocol</p>
          </div>
          <p className="text-red-500/60 text-[10px] leading-relaxed">
            API keys are stored securely in the backend .env file and never exposed to the frontend. GitHub repo URLs are stored locally in your browser.
          </p>
        </div>
      </div>
    </div>
  );
}