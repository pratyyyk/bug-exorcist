import docker
import os
import tarfile
import io
import time
from typing import Optional, Tuple

class DockerManager:
    def __init__(self):
        
        try:
            self.client = docker.from_env()
        except docker.errors.DockerException as e:
            print(f"Error initializing Docker client: {e}")
            raise

    def create_container(self, image: str = "python:3.9-slim") -> str:
        
        try:
        
            try:
                self.client.images.get(image)
            except docker.errors.ImageNotFound:
                print(f"Image {image} not found, pulling...")
                self.client.images.pull(image)


            container = self.client.containers.run(
                image,
                detach=True,
                tty=True,  
                stdin_open=True, 
                network_disabled=False, 
                
            )
            return container.id
        except Exception as e:
            print(f"Error creating container: {e}")
            raise


    def execute_code(self, container_id: str, code: str, timeout: int = 10) -> Tuple[int, str]:
        
        import subprocess
        
        script_name = "unsafe_script.py"
        remote_path = f"/app/{script_name}"

        try:
            
            subprocess.run(["docker", "exec", container_id, "mkdir", "-p", "/app"], check=False)

            
            cmd = ["docker", "exec", "-i", container_id, "sh", "-c", f"cat > {remote_path}"]
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(input=code.encode('utf-8'))
            
            if process.returncode != 0:
                return process.returncode, f"Failed to write code ({process.returncode}): {stderr.decode('utf-8')}"

            
            exec_cmd = ["docker", "exec", container_id, "python", remote_path]
            result = subprocess.run(exec_cmd, capture_output=True, text=True) 
            
            return result.returncode, result.stdout + result.stderr

        except Exception as e:
            return -1, str(e)

    def cleanup(self, container_id: str):
        """
        Stops and removes the container.
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            container.remove()
        except Exception as e:
            print(f"Error cleaning up container {container_id}: {e}")
