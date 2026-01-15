import docker
import tarfile
import io
import time

class Sandbox:
    def __init__(self, image="python:3.9-slim"):
        self.client = docker.from_env()
        self.image = image

    def run_code(self, code: str, language: str = "python") -> str:
        """
        Executes code in a secure Docker sandbox.
        """
        container = None
        try:
            # Configure resource limits
            # 512MB Memory Limit
            mem_limit = "512m"
            # 0.5 CPU Limit (500,000,000 nano cpus)
            nano_cpus = 500_000_000
            
            # Create the container with restrictions
            container = self.client.containers.run(
                self.image,
                command="python -c \"import sys; exec(sys.stdin.read())\"",
                stdin_open=True,
                detach=True,
                # Security restrictions
                network_mode="none",  # Disable network
                mem_limit=mem_limit,  # Limit RAM
                nano_cpus=nano_cpus,  # Limit CPU
                # Drop all capabilities for extra security
                cap_drop=["ALL"] 
            )

           
            sock = container.attach_socket(params={'stdin': 1, 'stream': 1})
            sock.send(code.encode('utf-8'))
            sock.close() 

            
            try:
                result = container.wait(timeout=30)
                exit_code = result['StatusCode']
            except Exception as e:
                
                container.kill()
                return "Error: Execution timed out (30s limit)."

            # Get logs
            logs = container.logs().decode('utf-8')
            
            if exit_code != 0:
                return f"Error (Exit Code {exit_code}):\n{logs}"
            
            return logs

        except Exception as e:
            return f"System Error: {str(e)}"
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
