from app import create_app, socketio
import os
import subprocess

app = create_app()

def kill_port(port):
    try:
        # Find the process ID (PID) using the port
        result = subprocess.run(f"netstat -ano | findstr :{port}", shell=True, capture_output=True, text=True)
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    local_addr = parts[1]
                    pid = parts[-1]
                    if local_addr.endswith(f":{port}") and pid != "0":
                        print(f"Killing process {pid} on port {port}...")
                        subprocess.run(f"taskkill /PID {pid} /F", shell=True)
    except Exception as e:
        print(f"Error killing port {port}: {e}")

if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        kill_port(5000)
    socketio.run(app, debug=True)
