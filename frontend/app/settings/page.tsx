"use client";
// This component will be used once the frontend is initialized with Next.js

import { useEffect, useState } from "react";

export default function SettingsPage() {
  const [openaiKey, setOpenaiKey] = useState("");
  const [githubRepo, setGithubRepo] = useState("");

  useEffect(() => {
    setOpenaiKey(localStorage.getItem("openai_api_key") || "");
    setGithubRepo(localStorage.getItem("github_repo_url") || "");
  }, []);

  const saveSettings = () => {
    localStorage.setItem("openai_api_key", openaiKey);
    localStorage.setItem("github_repo_url", githubRepo);
  };

  return (
    <div style={{ padding: "2rem" }}>
      <h1>Settings</h1>

      <div style={{ marginTop: "1rem" }}>
        <label>OpenAI API Key</label>
        <br />
        <input
          type="password"
          value={openaiKey}
          onChange={(e) => setOpenaiKey(e.target.value)}
        />
      </div>

      <div style={{ marginTop: "1rem" }}>
        <label>GitHub Repository URL</label>
        <br />
        <input
          type="text"
          value={githubRepo}
          onChange={(e) => setGithubRepo(e.target.value)}
        />
      </div>

      <button style={{ marginTop: "1.5rem" }} onClick={saveSettings}>
        Save
      </button>
    </div>
  );
}
