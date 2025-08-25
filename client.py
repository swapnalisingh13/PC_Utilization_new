import psutil
import platform
import requests
import time
from datetime import datetime
import os
import shutil
import ctypes
import win32api
import win32gui
import win32process
import winreg
import socket
import wmi

#below is here for testing in the laptop
#STATIC_ENDPOINT = "http://127.0.0.1:5000/add_static"
#DYNAMIC_ENDPOINT = "http://127.0.0.1:5000/add_dynamic"

#testing through office pc
#STATIC_ENDPOINT = "https://mzknxfbr-5000.inc1.devtunnels.ms/add_static"
#DYNAMIC_ENDPOINT = "https://mzknxfbr-5000.inc1.devtunnels.ms/add_dynamic"
#my laptop wifi ipv4 address- 192.168.0.169

STATIC_ENDPOINT = "http://192.168.0.221:6060/add_static"
DYNAMIC_ENDPOINT = "http://192.168.0.221:6060/add_dynamic"
#used port 6060 for deployment pc
__version__= "v2.1"

SECRET_KEY = "my_super_secret_key_123"


# ---------------- GPU SETUP ----------------
try:
    import pynvml
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        nvml_path = os.path.join(os.path.dirname(nvidia_smi), "nvml.dll")
        if os.path.exists(nvml_path):
            pynvml.nvmlLib = ctypes.CDLL(nvml_path)
            pynvml.nvmlInit()
            GPU_AVAILABLE = True
        else:
            print("[GPU CHECK] nvml.dll not found near nvidia-smi.exe")
            GPU_AVAILABLE = False
    else:
        print("[GPU CHECK] nvidia-smi not found in PATH")
        GPU_AVAILABLE = False
except Exception as e:
    print("[GPU CHECK] No NVIDIA GPU detected or NVML not available:", e)
    GPU_AVAILABLE = False
# --------------------------------------------

def get_pc_name():
    return platform.node()

def get_static_data():
    cpu_model = platform.processor()
    logical_processors = psutil.cpu_count(logical=True)
    ram_size_gb = round(psutil.virtual_memory().total / (1024**3))
    storage_size_gb = round(psutil.disk_usage('/').total / (1024**3))
    os_version = f"{platform.system()} {platform.release()}"

    data = {
        'pc_name': get_pc_name(),
        'record_date': datetime.now().strftime('%Y-%m-%d'),
        'cpu_model': cpu_model,
        'logical_processors': logical_processors,
        'ram_size_gb': ram_size_gb,
        'storage_size_gb': storage_size_gb,
        'os_version': os_version,
        'secret_key': SECRET_KEY
    }

    # --------- NEW STATIC FIELDS ---------
    try:
        data['ip_address'] = socket.gethostbyname(socket.gethostname())

        c = wmi.WMI()
        bios = c.Win32_BIOS()[0]
        board = c.Win32_BaseBoard()[0]

        data['bios_version'] = getattr(bios, "SMBIOSBIOSVersion", None)

        # -------- Expansion Slot Summary --------
        try:
            slots = c.Win32_SystemSlot()
            used = sum(1 for s in slots if getattr(s, "CurrentUsage", 0) == 4)   # 4 = In Use
            free = sum(1 for s in slots if getattr(s, "CurrentUsage", 0) == 3)   # 3 = Available
            data['expansion_slots_motherboard'] = f"{used} used, {free} free"
        except Exception as e:
            print("[SLOT ERROR]", e)
            data['expansion_slots_motherboard'] = "Unavailable"

        # Handle serial numbers with fallback
        def clean_serial(value):
            if not value or value.strip().lower() == "default string":
                return "Unavailable"
            return value

        data['system_serial_number'] = clean_serial(getattr(c.Win32_ComputerSystemProduct()[0], "IdentifyingNumber", None))
        data['motherboard_serial_number'] = clean_serial(getattr(board, "SerialNumber", None))
        data['bios_serial_number'] = clean_serial(getattr(bios, "SerialNumber", None))

        # --------- LOCATION (city + lat,long) ---------
        try:
            loc_res = requests.get("https://ipinfo.io/json", timeout=5).json()
            city = loc_res.get("city", "UnknownCity")
            loc = loc_res.get("loc", "0,0")  # "lat,long"
            data['pc_location'] = f"{city} ({loc})"
        except Exception as e:
            print("[LOCATION ERROR]", e)
            data['pc_location'] = "Unknown"

    except Exception as e:
        print("[STATIC EXTRA ERROR]", e)
    # ------------------------------------

    print("[STATIC DATA] Sending:", data)
    return data



def get_friendly_name_from_registry(exe_name):
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            fr"Software\Classes\Applications\{exe_name}"
        ) as key:
            friendly, _ = winreg.QueryValueEx(key, "FriendlyAppName")
            return friendly
    except Exception:
        pass

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            fr"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
        ) as key:
            path, _ = winreg.QueryValueEx(key, None)
            if path:
                return os.path.splitext(os.path.basename(path))[0]
    except Exception:
        pass

    return None


def get_window_title_from_pid(pid):
    titles = []

    def callback(hwnd, pid_to_check):
        try:
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid_to_check and win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    titles.append(title)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(callback, pid)
    return titles[0] if titles else None


def get_app_name_from_pid(pid):
    try:
        proc = psutil.Process(pid)
        exe = proc.exe()
        exe_name = os.path.basename(exe)

        try:
            info = win32api.GetFileVersionInfo(exe, '\\')
            desc = win32api.VerQueryValue(info, r'\StringFileInfo\040904b0\FileDescription')
            if desc:
                return desc
        except Exception:
            pass

        reg_name = get_friendly_name_from_registry(exe_name)
        if reg_name:
            return reg_name

        win_title = get_window_title_from_pid(pid)
        if win_title:
            return win_title

        return os.path.splitext(exe_name)[0]

    except Exception:
        try:
            return psutil.Process(pid).name().replace(".exe", "")
        except Exception:
            return "Unknown"


def get_top_process_by_cpu():
    processes = [(p.pid, p.info['cpu_percent']) for p in psutil.process_iter(['pid', 'cpu_percent'])]
    if not processes:
        return None
    top_pid = max(processes, key=lambda x: x[1])[0]
    return get_app_name_from_pid(top_pid)

def get_top_process_by_ram():
    processes = [(p.pid, p.info['memory_percent']) for p in psutil.process_iter(['pid', 'memory_percent'])]
    if not processes:
        return None
    top_pid = max(processes, key=lambda x: x[1])[0]
    return get_app_name_from_pid(top_pid)

def get_gpu_utilization_and_process():
    if not GPU_AVAILABLE:
        return 0.0, None

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_percent = float(util.gpu)

        processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
        if processes:
            processes = sorted(processes, key=lambda p: (p.usedGpuMemory or 0), reverse=True)
            top_pid = processes[0].pid
            top_gpu_process = get_app_name_from_pid(top_pid)
        else:
            top_gpu_process = None

        return gpu_percent, top_gpu_process

    except Exception:
        return 0.0, None


def get_dynamic_data():
    gpu_util, gpu_status = get_gpu_utilization_and_process()

    data = {
        'pc_name': get_pc_name(),
        'record_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cpu_utilization_percent': psutil.cpu_percent(interval=1),
        'ram_utilization_percent': psutil.virtual_memory().percent,
        'gpu_utilization_percent': gpu_util,
        'top_cpu_process': get_top_process_by_cpu(),
        'top_ram_process': get_top_process_by_ram(),
        'top_gpu_process': gpu_status if gpu_status else None,
        'secret_key': SECRET_KEY
    }

    # -------- NEW DYNAMIC FIELDS --------
    try:
        data['disk_usage_percent'] = psutil.disk_usage('/').percent

        net1 = psutil.net_io_counters()
        sent1, recv1 = net1.bytes_sent, net1.bytes_recv
        time.sleep(1)
        net2 = psutil.net_io_counters()
        sent2, recv2 = net2.bytes_sent, net2.bytes_recv
        bytes_per_sec = (sent2 - sent1) + (recv2 - recv1)
        data['ethernet_utilization_percent'] = round(bytes_per_sec / (1024 * 1024), 2)  # MB/s approx.
    except Exception as e:
        print("[DYNAMIC EXTRA ERROR]", e)
    # ------------------------------------

    print("[DYNAMIC DATA] Sending:", data)
    return data

def send_data(endpoint, data):
    try:
        response = requests.post(endpoint, json=data, timeout=5)
        print(f"[RESPONSE] {endpoint} ->", response.status_code, response.json())
    except Exception as e:
        print(f"[ERROR] Failed to send {endpoint} data:", str(e))

def main():
    static_data = get_static_data()
    send_data(STATIC_ENDPOINT, static_data)

    while True:
        dynamic_data = get_dynamic_data()
        send_data(DYNAMIC_ENDPOINT, dynamic_data)
        time.sleep(60)  # Every 1 minutes

if __name__ == "__main__":
    main()
