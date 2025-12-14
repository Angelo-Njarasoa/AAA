from flask import Flask, render_template
import psutil
import platform
import socket
import time
import os

app = Flask(__name__)

# --------- FONCTIONS UTILITAIRES ---------

def get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "N/A"

def get_top_processes():
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append({
                "name": p.info['name'],
                "cpu": p.info['cpu_percent'],
                "ram": round(p.info['memory_percent'], 2)
            })
        except:
            pass

    top = sorted(processes, key=lambda x: x['cpu'], reverse=True)[:3]
    return top

def analyze_files(path):
    counts = {
        ".txt": 0,
        ".py": 0,
        ".pdf": 0,
        ".jpg": 0
    }
    total = 0

    for root, dirs, files in os.walk(path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in counts:
                counts[ext] += 1
                total += 1

    percentages = {}
    for ext in counts:
        if total > 0:
            percentages[ext] = round((counts[ext] / total) * 100, 2)
        else:
            percentages[ext] = 0

    return counts, percentages, total

# --------- ROUTE PRINCIPALE ---------

@app.route("/")
def home():
    uname = platform.uname()

    uptime_seconds = time.time() - psutil.boot_time()
    uptime_minutes = int(uptime_seconds / 60)

    cpu = psutil.cpu_freq()
    ram = psutil.virtual_memory()

    processes = get_top_processes()

    file_path = f"/home/{os.getenv('USER')}"
    file_counts, file_percentages, total_files = analyze_files(file_path)

    return render_template("template.html",
        # Système
        machine_name=uname.node,
        system_name=f"{uname.system} {uname.release}",
        boot_time=time.ctime(psutil.boot_time()),
        uptime=uptime_minutes,
        users_count=len(psutil.users()),
        ip_address=get_ip(),

        # CPU
        cpu_cores=psutil.cpu_count(),
        cpu_freq=round(cpu.current, 2),
        cpu_usage=psutil.cpu_percent(interval=1),

        # RAM
        ram_total=round(ram.total / (1024**3), 2),
        ram_used=round(ram.used / (1024**3), 2),
        ram_percent=ram.percent,

        # Processus
        process1=f"{processes[0]['name']} - CPU {processes[0]['cpu']}% - RAM {processes[0]['ram']}%",
        process2=f"{processes[1]['name']} - CPU {processes[1]['cpu']}% - RAM {processes[1]['ram']}%",
        process3=f"{processes[2]['name']} - CPU {processes[2]['cpu']}% - RAM {processes[2]['ram']}%",

        # Fichiers
        txt_count=file_counts[".txt"],
        py_count=file_counts[".py"],
        pdf_count=file_counts[".pdf"],
        jpg_count=file_counts[".jpg"],

        txt_percent=file_percentages[".txt"],
        py_percent=file_percentages[".py"],
        pdf_percent=file_percentages[".pdf"],
        jpg_percent=file_percentages[".jpg"],
        total_files=total_files
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
