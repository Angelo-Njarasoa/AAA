from flask import Flask, render_template
import psutil
import platform
import socket
import time
import os
import locale
from datetime import datetime
import heapq

app = Flask(__name__)

# --------- LOCALE FRANÇAISE ---------
try:
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "fr")
    except:
        pass  # fallback : laisser comme ça si impossible

# --------- UTILITAIRES ---------

def get_ip():
    """Retourne l'IP réseau locale (pas 127.0.0.1)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "N/A"

def human_size(nbytes):
    """Convertit des octets en format lisible"""
    suffixes = ['o', 'Ko', 'Mo', 'Go', 'To', 'Po']
    if nbytes == 0:
        return "0 o"
    i = 0
    n = float(nbytes)
    while n >= 1024 and i < len(suffixes)-1:
        n /= 1024.
        i += 1
    if i == 0:
        return f"{int(n)} {suffixes[i]}"
    return f"{n:.2f} {suffixes[i]}"

def get_top_processes():
    """Retourne le top 3 des processus par CPU"""
    processes = []
    # Première passe: collecter info rapide (cpu_percent requires an interval)
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append({
                "name": p.info['name'] or str(p.info['pid']),
                "cpu": p.info['cpu_percent'],
                "ram": round(p.info['memory_percent'], 2)
            })
        except Exception:
            pass
    top = sorted(processes, key=lambda x: x['cpu'] or 0, reverse=True)[:3]
    return top

def analyze_files_deep(path, extensions=None, top_n=10):
    """
    Parcourt récursivement path, compte fichiers par extension (extensions
    est une liste d'extensions à analyser), calcule taille totale par type,
    et retourne les top_n fichiers par taille.
    """
    if extensions is None:
        extensions = [
            ".txt", ".py", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".log", ".csv",
            ".zip", ".tar", ".gz", ".mp4", ".mkv", ".docx", ".xlsx", ".pptx", ".json"
        ]

    counts = {ext: 0 for ext in extensions}
    sizes = {ext: 0 for ext in extensions}
    total_files = 0
    total_size = 0

    # min-heap pour top files (taille, path)
    top_heap = []

    for root, dirs, files in os.walk(path):
        for fname in files:
            total_files += 1
            fpath = os.path.join(root, fname)
            try:
                st = os.path.getsize(fpath)
            except Exception:
                continue
            total_size += st
            ext = os.path.splitext(fname)[1].lower()
            if ext in counts:
                counts[ext] += 1
                sizes[ext] += st
            # maintenir top_n
            if len(top_heap) < top_n:
                heapq.heappush(top_heap, (st, fpath))
            else:
                if st > top_heap[0][0]:
                    heapq.heapreplace(top_heap, (st, fpath))

    # convertir heap en liste triée décroissante
    top_files = sorted(top_heap, key=lambda x: x[0], reverse=True)

    # calculer pourcentage en nombre et en taille
    counts_percent = {}
    sizes_percent = {}
    for ext in extensions:
        counts_percent[ext] = round((counts[ext] / total_files) * 100, 2) if total_files > 0 else 0
        sizes_percent[ext] = round((sizes[ext] / total_size) * 100, 2) if total_size > 0 else 0

    return {
        "counts": counts,
        "counts_percent": counts_percent,
        "sizes": sizes,
        "sizes_percent": sizes_percent,
        "total_files": total_files,
        "total_size": total_size,
        "top_files": [(p, s) for (s, p) in top_files]  # (path, size)
    }

def format_uptime(seconds):
    """Format uptime propre en français"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days} jour{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} heure{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    parts.append(f"{secs} seconde{'s' if secs > 1 else ''}")

    return " ".join(parts)

# --------- ROUTE PRINCIPALE ---------

@app.route("/")
def home():
    uname = platform.uname()

    # Uptime
    uptime_seconds = int(time.time() - psutil.boot_time())
    uptime_str = format_uptime(uptime_seconds)

    # Boot time en FR
    boot_dt = datetime.fromtimestamp(psutil.boot_time())
    try:
        boot_time_str = boot_dt.strftime("%A %d %B %Y à %H:%M:%S")
    except Exception:
        boot_time_str = boot_dt.isoformat(sep=' ')

    # CPU : load averages
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1 = load5 = load15 = 0.0

    # CPU : pourcentage par cœur (bloquant 1s pour mesurer)
    per_core = psutil.cpu_percent(interval=1, percpu=True)

    # CPU global
    cpu_usage = psutil.cpu_percent(interval=0.1)

    # RAM
    ram = psutil.virtual_memory()

    # Disk global
    disk = psutil.disk_usage("/")

    # Processus (top)
    processes = get_top_processes()
    p1 = processes[0] if len(processes) > 0 else None
    p2 = processes[1] if len(processes) > 1 else None
    p3 = processes[2] if len(processes) > 2 else None

    # Analyse fichiers approfondie (répertoire utilisateur)
    file_path = f"/home/{os.getenv('USER')}" if os.getenv('USER') else "/"
    file_report = analyze_files_deep(file_path, top_n=10)

    # Construire la liste d'extensions avec données pour Jinja
    ext_rows = []
    for ext in file_report["counts"].keys():
        ext_rows.append({
            "ext": ext,
            "count": file_report["counts"][ext],
            "count_percent": file_report["counts_percent"][ext],
            "size": file_report["sizes"][ext],
            "size_hr": human_size(file_report["sizes"][ext]),
            "size_percent": file_report["sizes_percent"][ext]
        })

    # Top fichiers (path, size) en format lisible
    top_files_hr = [{"path": p, "size": s, "size_hr": human_size(s)} for p, s in file_report["top_files"]]

    # timestamp génération
    gen_dt = datetime.now()
    try:
        gen_str = gen_dt.strftime("%A %d %B %Y à %H:%M:%S")
    except Exception:
        gen_str = gen_dt.isoformat(sep=' ')

    return render_template("template.html",
        # Système
        machine_name=uname.node,
        system_name=f"{uname.system} {uname.release}",
        boot_time=boot_time_str,
        uptime=uptime_str,
        users_count=len(psutil.users()),
        ip_address=get_ip(),
        generated_at=gen_str,

        # Load averages
        load1=round(load1, 2),
        load5=round(load5, 2),
        load15=round(load15, 2),

        # CPU
        cpu_cores=psutil.cpu_count(logical=True),
        per_core=per_core,
        cpu_usage=cpu_usage,

        # RAM
        ram_total=round(ram.total / (1024**3), 2),
        ram_used=round(ram.used / (1024**3), 2),
        ram_percent=ram.percent,

        # Disk
        disk_total=round(disk.total / (1024**3), 2),
        disk_used=round(disk.used / (1024**3), 2),
        disk_percent=disk.percent,

        # Processus
        process1=f"{p1['name']} - CPU {p1['cpu']}% - RAM {p1['ram']}%" if p1 else "Aucun processus",
        process2=f"{p2['name']} - CPU {p2['cpu']}% - RAM {p2['ram']}%" if p2 else "Aucun processus",
        process3=f"{p3['name']} - CPU {p3['cpu']}% - RAM {p3['ram']}%" if p3 else "Aucun processus",

        # Fichiers approfondis
        ext_rows=ext_rows,
        total_files=file_report["total_files"],
        total_size_hr=human_size(file_report["total_size"]),
        top_files=top_files_hr
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
