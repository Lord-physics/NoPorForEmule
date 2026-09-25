from __future__ import annotations

import os
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .monitor import Monitor
from .partmeta import download_name
from .scanner import ScanResult
from .startup import desktop_shortcut, set_startup, startup_enabled
from .storage import Settings, app_data_dir

STATUS_TEXT = {
    "possible": "Posible contenido pornográfico",
    "clear": "Sin indicios detectados",
    "unscanned": "No analizado",
}


def confirm_and_open(path: Path, result: ScanResult, ask=messagebox.askyesno, opener=os.startfile) -> bool:
    if not path.is_file():
        return False
    if result.status == "possible":
        text = "Posible contenido pornográfico. ¿Quieres abrir este archivo?"
    elif result.status == "clear":
        text = "No se detectaron indicios en lo analizado. Esto no garantiza que todo el archivo esté libre de ese contenido. ¿Abrir?"
    else:
        text = "Archivo no analizado. Podría contener pornografía. ¿Quieres abrirlo?"
    if not ask("Aviso antes de abrir", text, icon="warning"):
        return False
    opener(str(path))
    return True


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NoPorForEmule")
        self.geometry("940x550")
        self.events: queue.Queue = queue.Queue()
        self.settings = Settings(app_data_dir())
        self.settings_data = self.settings.load()
        self.monitor = Monitor(app_data_dir(), self.events)
        self.results: dict[Path, ScanResult] = {}
        self.paths: dict[str, Path] = {}
        self.alerted_parts: set[Path] = set()
        self.incoming_label = tk.StringVar(value="Incoming: sin configurar")
        self.temp_label = tk.StringVar(value="Temp: sin configurar")
        self.emule_label = tk.StringVar(value="eMule.exe: sin configurar")
        self.message = tk.StringVar(value="Solo se abrirán archivos desde este programa cuando lo confirmes.")
        self.joint_launcher = Path(__file__).resolve().parents[1] / "IniciarConEmule.bat"
        self.autostart = tk.BooleanVar(value=startup_enabled(self.joint_launcher))
        self._build()
        self.after(150, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._set_folders()

    def _build(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        for label, button, command in (
            (self.incoming_label, "Elegir Incoming", lambda: self._choose("incoming")),
            (self.temp_label, "Elegir Temp", lambda: self._choose("temp")),
            (self.emule_label, "Elegir eMule.exe", self._choose_emule),
        ):
            row = ttk.Frame(top)
            row.pack(fill="x")
            ttk.Label(row, textvariable=label).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text=button, command=command).pack(side="right")
        options = ttk.Frame(top)
        options.pack(fill="x", pady=(8, 0))
        ttk.Button(options, text="Crear acceso directo en escritorio", command=self._desktop_shortcut).pack(side="left")
        ttk.Checkbutton(options, text="Iniciar ambos al entrar en Windows", variable=self.autostart,
                        command=self._toggle_startup).pack(side="left", padx=12)
        columns = ("name", "status", "detail")
        self.table = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        for key, label, width in (("name", "Archivo", 360), ("status", "Estado", 230), ("detail", "Detalle", 280)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width)
        self.table.pack(fill="both", expand=True, padx=12)
        self.table.bind("<Double-1>", lambda _event: self._open())
        bottom = ttk.Frame(self, padding=12)
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.message, wraplength=650).pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Abrir seleccionado…", command=self._open).pack(side="right")

    def _choose(self, kind: str):
        chosen = filedialog.askdirectory(title=f"Selecciona {kind} de eMule")
        if chosen:
            self.settings_data[kind] = chosen
            self.settings.save(self.settings_data)
            self._set_folders()

    def _set_folders(self):
        incoming = Path(self.settings_data["incoming"]) if self.settings_data.get("incoming") else None
        temp = Path(self.settings_data["temp"]) if self.settings_data.get("temp") else None
        self.incoming_label.set(f"Incoming: {incoming or 'sin configurar'}")
        self.temp_label.set(f"Temp: {temp or 'sin configurar'}")
        self.emule_label.set(f"eMule.exe: {self.settings_data.get('emule') or 'sin configurar'}")
        self.results.clear()
        self.paths.clear()
        self.alerted_parts.clear()
        for row in self.table.get_children():
            self.table.delete(row)
        if incoming or temp:
            self.monitor.start(incoming, temp)

    def _choose_emule(self):
        chosen = filedialog.askopenfilename(title="Selecciona eMule.exe", filetypes=[("eMule", "eMule.exe")])
        if chosen:
            if Path(chosen).name.lower() != "emule.exe":
                messagebox.showerror("Archivo incorrecto", "Selecciona eMule.exe")
                return
            self.settings_data["emule"] = chosen
            self.settings.save(self.settings_data)
            self.emule_label.set(f"eMule.exe: {chosen}")

    def _ready_for_joint_launch(self) -> bool:
        path = Path(self.settings_data.get("emule", ""))
        if path.is_file() and path.name.lower() == "emule.exe":
            return True
        messagebox.showerror("Falta eMule", "Selecciona eMule.exe antes de activar el inicio conjunto.")
        return False

    def _desktop_shortcut(self):
        if not self._ready_for_joint_launch():
            return
        try:
            path = desktop_shortcut(self.joint_launcher)
            self.message.set(f"Acceso directo creado: {path}")
        except Exception as exc:
            messagebox.showerror("No se pudo crear el acceso directo", str(exc))

    def _toggle_startup(self):
        enabled = self.autostart.get()
        if enabled and not self._ready_for_joint_launch():
            self.autostart.set(False)
            return
        try:
            set_startup(self.joint_launcher, enabled)
        except Exception as exc:
            self.autostart.set(not enabled)
            messagebox.showerror("No se pudo cambiar el inicio automático", str(exc))

    def _drain(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "message":
                    self.message.set(event[1])
                elif event[0] == "remove":
                    path = event[1]
                    self.results.pop(path, None)
                    self.alerted_parts.discard(path)
                    for row, stored in list(self.paths.items()):
                        if stored == path:
                            self.table.delete(row)
                            del self.paths[row]
                else:
                    _, path, result = event
                    if path.parent not in (self.monitor.incoming, self.monitor.temp):
                        continue
                    self.results[path] = result
                    partial = path.parent == self.monitor.temp and path.suffix.lower() == ".part"
                    name = download_name(path) if partial else None
                    display = f"{name} ({path.name})" if name else path.name
                    values = (display, STATUS_TEXT[result.status], result.detail)
                    row = next((row for row, stored in self.paths.items() if stored == path), None)
                    if row:
                        self.table.item(row, values=values)
                    else:
                        row = self.table.insert("", "end", values=values)
                        self.paths[row] = path
                    if partial and result.status == "possible" and path not in self.alerted_parts:
                        self.alerted_parts.add(path)
                        self.bell()
                        messagebox.showwarning(
                            "Posible contenido pornográfico durante la descarga",
                            f"Descarga: {name or 'nombre no disponible'}\nTemporal: {path.name}\n"
                            "Se ha detectado un indicio en los datos disponibles. El archivo sigue descargándose.",
                        )
        except queue.Empty:
            pass
        self.after(150, self._drain)

    def _open(self):
        selected = self.table.selection()
        if not selected:
            self.message.set("Selecciona un archivo primero.")
            return
        path = self.paths[selected[0]]
        if path.parent == self.monitor.temp and path.suffix.lower() == ".part":
            messagebox.showinfo("Descarga incompleta", "El archivo temporal no se abre desde NoPorForEmule.")
            return
        result = self.results.get(path, ScanResult("unscanned", "Sin resultado"))
        try:
            if not confirm_and_open(path, result):
                self.message.set("Apertura cancelada o archivo no disponible.")
        except OSError as exc:
            messagebox.showerror("No se pudo abrir", str(exc))

    def _close(self):
        self.monitor.stop()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
