import asyncio
import random
from datetime import datetime

class BugExorcistAgent:
    def __init__(self, bug_id: str):
        self.bug_id = bug_id
        self.stages = [
            "Initializing sandbox environment...",
            "Cloning repository into isolated container...",
            "Installing dependencies...",
            "Running reproduction script...",
            "Analyzing stack trace...",
            "Identifying root cause with GPT-4o...",
            "Generating patch candidate...",
            "Applying patch...",
            "Verifying fix with unit tests...",
            "Fix verified. Cleaning up resources."
        ]

    async def stream_logs(self):
        """
        Simulates the autonomous agent's log output.
        In a real scenario, this would read from a Docker container's stdout
         or an LLM's thought process.
        """
        yield f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Starting exorcism for Bug ID: {self.bug_id}"
        
        for stage in self.stages:
            await asyncio.sleep(random.uniform(1.0, 3.0))
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            if "GPT-4o" in stage:
                yield f"[{timestamp}] [AI] {stage}"
            elif "Verifying" in stage:
                yield f"[{timestamp}] [TEST] {stage}"
            elif "verified" in stage:
                yield f"[{timestamp}] [SUCCESS] {stage}"
            else:
                yield f"[{timestamp}] [DEBUG] {stage}"
            
            # Add some extra "realistic" sub-logs
            if "dependencies" in stage:
                yield f"[{timestamp}] [DEBUG] Pip: Installing fastapi, langchain, openai..."
            elif "reproduction" in stage:
                yield f"[{timestamp}] [DEBUG] Traceback detected: ZeroDivisionError in main.py:42"
        
        yield f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Exorcism complete for {self.bug_id}."
