import subprocess
import psutil

# Configurable settings
task_name = "Run HPA Client"
batch_file = r"V:\_For Wasim Sir\dist\run_client.bat"
process_name = "client.exe"

def kill_program(proc_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc_name.lower() in proc.info['name'].lower():
            try:
                print(f"Killing {proc.info['name']} (PID: {proc.info['pid']})")
                psutil.Process(proc.info['pid']).terminate()
            except psutil.AccessDenied:
                print(f"Access denied for PID {proc.info['pid']}")
            except Exception as e:
                print(f"Failed to kill process: {e}")

kill_program(process_name)

# Create task
subprocess.run(
    f'schtasks /create /tn "{task_name}" /tr "{batch_file}" /sc onlogon /rl HIGHEST /f',
    shell=True
)

# Run task
subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True)

print("Task created and executed.")
