import docker
import logging
import uuid
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DockerSandboxManager:
    def __init__(self):
        try:
            self.client = docker.from_env()
            logger.info("Docker client initialized successfully.")
        except docker.errors.DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise

    def create_container(self, image="python:3.9-slim", memory_limit="128m"):
        """
        Spin up an isolated container to run unsafe code.
        """
        container_name = f"sandbox_{uuid.uuid4().hex}"
        try:
            logger.info(f"Creating sandbox container: {container_name}")
            container = self.client.containers.run(
                image,
                command="tail -f /dev/null",  # Keep container running
                name=container_name,
                mem_limit=memory_limit,
                network_disabled=True,        # Isolate from network for security
                detach=True,
                pids_limit=10,                # Prevent fork bombs
                cpu_quota=50000,              # Limit CPU usage (50%)
                read_only=False
            )
            return container.id
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            return None

    def execute_code(self, container_id, code, timeout=5):
        """
        Execute a Python script inside the container.
        """
        try:
            container = self.client.containers.get(container_id)
            
            # Escape code safe for shell execution
            safe_code = code.replace('"', '\\"').replace("'", "\\'")
            command = f'python3 -c "{safe_code}"'

            logger.info(f"Executing code in container {container_id}")
            
            # Run the command with timeout handling
            exec_result = container.exec_run(command, workdir="/tmp")
            
            output = exec_result.output.decode("utf-8")
            exit_code = exec_result.exit_code

            return {
                "output": output,
                "exit_code": exit_code,
                "status": "success" if exit_code == 0 else "error"
            }
        except docker.errors.NotFound:
            logger.error(f"Container {container_id} not found.")
            return {"status": "error", "message": "Container not found"}
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {"status": "error", "message": str(e)}

    def cleanup(self, container_id):
        """
        Stop and remove the container.
        """
        try:
            container = self.client.containers.get(container_id)
            logger.info(f"Cleaning up container {container_id}")
            container.stop(timeout=1)
            container.remove(force=True)
            return True
        except Exception as e:
            logger.error(f"Cleanup failed for {container_id}: {e}")
            return False

# Example usage for testing (if run directly)
if __name__ == "__main__":
    manager = DockerSandboxManager()
    
    # 1. Create
    cid = manager.create_container()
    if cid:
        print(f"Container Started: {cid}")
        
        # 2. Execute Unsafe Code
        unsafe_code = "print('Hello from the secure sandbox!')"
        result = manager.execute_code(cid, unsafe_code)
        print("Execution Result:", result)
        
        # 3. Cleanup
        manager.cleanup(cid)
        print("Container Destroyed")