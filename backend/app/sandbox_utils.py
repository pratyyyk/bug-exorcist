import os
import yaml
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SandboxManifest:
    def __init__(self, 
                 env: Dict[str, str] = None, 
                 resources: Dict[str, Any] = None, 
                 setup_scripts: List[str] = None,
                 services: List[Dict[str, Any]] = None,
                 volumes: Dict[str, str] = None):
        self.env = env or {}
        self.resources = resources or {}
        self.setup_scripts = setup_scripts or []
        self.services = services or []
        self.volumes = volumes or {}

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'SandboxManifest':
        if not os.path.exists(yaml_path):
            return cls()
        
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f) or {}
                return cls(
                    env=data.get('env', {}),
                    resources=data.get('resources', {}),
                    setup_scripts=data.get('setup', []),
                    services=data.get('services', []),
                    volumes=data.get('volumes', {})
                )
        except Exception as e:
            logger.error(f"Error parsing .exorcist.yaml: {e}")
            return cls()

def detect_project_type(project_path: str) -> Optional[str]:
    if os.path.exists(os.path.join(project_path, 'requirements.txt')):
        return 'python'
    if os.path.exists(os.path.join(project_path, 'package.json')):
        return 'nodejs'
    if os.path.exists(os.path.join(project_path, 'go.mod')):
        return 'go'
    return None

def generate_dynamic_dockerfile(project_path: str, manifest: SandboxManifest, base_image: str = "bug-exorcist-sandbox:latest") -> str:
    project_type = detect_project_type(project_path)
    dockerfile_lines = [
        f"FROM {base_image}",
        "USER root",
        "WORKDIR /app"
    ]
    
    # Add environment variables
    for key, value in manifest.env.items():
        dockerfile_lines.append(f"ENV {key}={value}")
    
    # Project-specific setup with optimized layer caching
    if project_type == 'python':
        dockerfile_lines.append("COPY requirements.txt .")
        dockerfile_lines.append("RUN pip install --no-cache-dir -r requirements.txt")
    elif project_type == 'nodejs':
        dockerfile_lines.append("COPY package*.json ./")
        dockerfile_lines.append("RUN npm install --no-audit --no-fund")
    elif project_type == 'go':
        dockerfile_lines.append("COPY go.mod go.sum* ./")
        dockerfile_lines.append("RUN go mod download")

    # Custom setup scripts from manifest
    for script in manifest.setup_scripts:
        dockerfile_lines.append(f"RUN {script}")
    
    # Security: Create and switch to non-root user for execution
    dockerfile_lines.extend([
        "RUN useradd -m exorcist && chown -R exorcist:exorcist /app",
        "USER exorcist"
    ])
    
    return "\n".join(dockerfile_lines)
