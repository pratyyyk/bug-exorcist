import git
import os
from typing import Optional

def apply_fix_to_repo(
    repo_path: str, bug_id: str, file_path: str, fixed_code: str
) -> str:
    """
    Applies a fix to the repository by creating a new branch, updating the file, and committing.
    """
    try:
        repo = git.Repo(repo_path)
        
    

        branch_name = f"fix/bug-{bug_id}"
        
        # Create or checkout branch
        if branch_name in repo.heads:
            current = repo.heads[branch_name]
            current.checkout()
        else:
            current = repo.create_head(branch_name)
            current.checkout()
            
        # Full path to the file
        full_file_path = os.path.join(repo_path, file_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
        
        # Write the fixed code
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(fixed_code)
            
        # Git operations
        repo.index.add([full_file_path])
        repo.index.commit(f"fix: applied fix for bug {bug_id}")
        
        return f"Success: Fix applied on branch {branch_name}"
        
    except Exception as e:
        return f"Error applying fix: {str(e)}"
