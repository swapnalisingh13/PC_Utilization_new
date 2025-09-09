import subprocess
import psutil

# Task details
task_name = "Run HPA Client"                 #task name to run as
batch_file = r"C:\path\to\your\script.bat"   # change this to your .bat file
process_name = "client.exe"                  # process to kill before running

# 1. Kill process if running
def kill_program(proc_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc_name.lower() in proc.info['name'].lower():
            print(f"Killing {proc.info['name']} (PID: {proc.info['pid']})")
            psutil.Process(proc.info['pid']).terminate()

kill_program(process_name)

# 2. Create/Update scheduled task
subprocess.run(
    f'schtasks /create /tn "{task_name}" /tr "{batch_file}" /sc onlogon /rl HIGHEST /f',
    shell=True
)

# 3. Run the task immediately
subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True)

print(f"Task '{task_name}' created, old '{process_name}' killed (if running), and started successfully.")
