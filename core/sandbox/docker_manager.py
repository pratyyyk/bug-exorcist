import docker
import logging
import uuid
import threading
import time

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
        Changes for Security:
        - read_only=True: Root filesystem is immutable (prevents persistence/rootkits).
        - tmpfs: Writable temporary directory limited to 64MB (prevents disk fill attacks).
        - user="nobody": Run as non-privileged user.
        - cap_drop=["ALL"]: Drop all capabilities.
        - security_opt=["no-new-privileges"]: Prevent privilege escalation.
        """
        container_name = f"sandbox_{uuid.uuid4().hex}"
        try:
            logger.info(f"Creating secure sandbox container: {container_name}")
            container = self.client.containers.run(
                image,
                command="tail -f /dev/null",  # Keep container running
                name=container_name,
                mem_limit=memory_limit,
                network_disabled=True,        # Isolate from network
                detach=True,
                pids_limit=10,                # Prevent fork bombs
                cpu_quota=50000,              # Limit CPU usage (50%)
                read_only=True,               # [Security] Make root FS read-only
                tmpfs={'/tmp': 'size=64m'},   # [Security] Limited writeable space
                user="nobody",                # [Security] Run as non-root user
                cap_drop=["ALL"],             # [Security] Drop all root capabilities
                security_opt=["no-new-privileges"] # [Security] Prevent privilege escalation
            )
            return container.id
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            return None

    def execute_code(self, container_id, code, timeout=5):
        """
        Execute a Python script inside the container securely.
        Changes for Security:
        - List-based command: Prevents shell injection.
        - Threaded Timeout: Enforces strict execution time limits.
        """
        try:
            container = self.client.containers.get(container_id)
            
            # [Security] Use list format to prevent Command Injection
            # No need to manually escape quotes; Docker SDK handles arguments safely.
            command = ["python3", "-c", code]
            
            result_holder = {}

            def run_exec():
                try:
                    # Execute in /tmp since root is read-only
                    exec_result = container.exec_run(command, workdir="/tmp")
                    result_holder['output'] = exec_result.output.decode("utf-8")
                    result_holder['exit_code'] = exec_result.exit_code
                except Exception as ex:
                    result_holder['error'] = str(ex)

            # [Security] Run execution in a separate thread to enforce timeout
            exec_thread = threading.Thread(target=run_exec)
            exec_thread.start()
            exec_thread.join(timeout=timeout)

            if exec_thread.is_alive():
                logger.warning(f"Timeout detected for container {container_id}. Restarting to clear state.")
                # If it's still running, the code is stuck (e.g., while True).
                # We restart the container to kill the process reliably.
                try:
                    container.restart(timeout=0)
                except Exception as restart_err:
                    logger.error(f"Failed to restart container: {restart_err}")
                
                return {
                    "output": "Error: Execution timed out.",
                    "exit_code": 124, # Standard UNIX timeout exit code
                    "status": "error"
                }

            if 'error' in result_holder:
                return {"status": "error", "message": result_holder['error']}

            exit_code = result_holder.get('exit_code', 1)
            return {
                "output": result_holder.get('output', ''),
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

if __name__ == "__main__":
    # Quick test to verify changes locally
    manager = DockerSandboxManager()
    cid = manager.create_container()
    if cid:
        print(f"Started: {cid}")
        
        # Test 1: Normal Code
        print("\nTest 1 (Normal):", manager.execute_code(cid, "print(sum(i for i in range(10)))"))
        
        # Test 2: Timeout Loop (Should return timeout error)
        print("\nTest 2 (Timeout):", manager.execute_code(cid, "while True: pass", timeout=2))
        
        # Test 3: File Write (Should work in /tmp)
        code_file = "with open('/tmp/test.txt', 'w') as f: f.write('ok'); print('wrote file')"
        print("\nTest 3 (Tmp Write):", manager.execute_code(cid, code_file))
        
        manager.cleanup(cid)