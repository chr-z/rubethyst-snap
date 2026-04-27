from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from queue import Queue
from tkinter import messagebox, ttk

from ..core import ProgressEvent, ProgressStatus, RubethystError, download


class RubethystDesktopApp:
    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        master.title("Rubethyst Snap")
        master.geometry("420x520")
        master.configure(bg="#f5f5f7")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Main.TFrame", background="#f5f5f7")
        style.configure("Title.TLabel", font=("SF Pro Display", 22, "bold"),
                        background="#f5f5f7", foreground="#1d1d1f")
        style.configure("Info.TLabel", font=("SF Pro Text", 11),
                        background="#f5f5f7", foreground="#1d1d1f")
        style.configure("Eta.TLabel", font=("SF Pro Text", 10),
                        background="#f5f5f7", foreground="#86868b")
        style.configure("Link.TEntry", font=("SF Pro Text", 11), padding=8)
        style.configure("TProgressbar", thickness=6, background="#0071e3",
                        troughcolor="#e0e0e0")

        frame = ttk.Frame(master, style="Main.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(frame, text="Rubethyst Snap", style="Title.TLabel").pack(pady=(0, 16))

        self.link_entry = ttk.Entry(frame, style="Link.TEntry")
        self.link_entry.pack(fill=tk.X, pady=(0, 12))
        self.link_entry.insert(0, "Cole o link do vídeo aqui")
        self.link_entry.bind("<FocusIn>", self._clear_placeholder)
        self.link_entry.bind("<FocusOut>", self._restore_placeholder)

        preset_row = ttk.Frame(frame, style="Main.TFrame")
        preset_row.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(preset_row, text="Formato:", style="Info.TLabel").pack(side=tk.LEFT)
        self.preset_var = tk.StringVar(value="smart_1080")
        ttk.Combobox(
            preset_row,
            textvariable=self.preset_var,
            values=["smart_1080", "mp4", "best", "1080p", "720p", "audio", "mp3"],
            state="readonly",
            width=12,
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(
            frame,
            text="Adicionar à fila",
            command=self.add_to_queue,
            bg="#0071e3",
            fg="white",
            relief=tk.FLAT,
            padx=12,
            pady=6,
        ).pack(pady=(0, 12))

        self.queue_label = ttk.Label(frame, text="Fila: 0", style="Info.TLabel")
        self.queue_label.pack(pady=(0, 8))

        self.title_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.title_var, style="Info.TLabel",
                  wraplength=360).pack(anchor="w")

        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, style="Info.TLabel").pack(anchor="w")

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(frame, variable=self.progress_var, maximum=100,
                        style="TProgressbar").pack(fill=tk.X, pady=(8, 4))

        self.eta_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.eta_var, style="Eta.TLabel").pack(anchor="e")

        self.queue: Queue[tuple[str, str]] = Queue()
        self.busy = False

    def _clear_placeholder(self, _event: tk.Event) -> None:
        if self.link_entry.get() == "Cole o link do vídeo aqui":
            self.link_entry.delete(0, tk.END)

    def _restore_placeholder(self, _event: tk.Event) -> None:
        if not self.link_entry.get():
            self.link_entry.insert(0, "Cole o link do vídeo aqui")

    def add_to_queue(self) -> None:
        link = self.link_entry.get().strip()
        if not link or link == "Cole o link do vídeo aqui":
            messagebox.showerror("Erro", "Por favor, insira um link.")
            return
        self.queue.put((link, self.preset_var.get()))
        self.queue_label.config(text=f"Fila: {self.queue.qsize()}")
        self.link_entry.delete(0, tk.END)
        self.link_entry.insert(0, "Cole o link do vídeo aqui")
        if not self.busy:
            self._next()

    def _next(self) -> None:
        if self.queue.empty():
            self.busy = False
            return
        self.busy = True
        link, preset = self.queue.get()
        date_folder = datetime.now().strftime("%Y-%m-%d")
        out = os.path.join(os.path.expanduser("~"), "Downloads", "RubethystSnap", date_folder)
        os.makedirs(out, exist_ok=True)
        self.progress_var.set(0)
        self.title_var.set("")
        self.status_var.set("Iniciando…")
        self.eta_var.set("")
        threading.Thread(target=self._run, args=(link, preset, out), daemon=True).start()

    def _run(self, link: str, preset: str, out: str) -> None:
        try:
            download(link, out, preset=preset, progress=self._dispatch)
            self.master.after(0, lambda: self.status_var.set("Concluído"))
        except RubethystError as exc:
            self.master.after(0, lambda: self.status_var.set(f"Erro: {exc}"))
        except Exception as exc:
            self.master.after(0, lambda: self.status_var.set(f"Erro inesperado: {exc}"))
        finally:
            self.master.after(0, self._done)

    def _dispatch(self, event: ProgressEvent) -> None:
        self.master.after(0, self._apply, event)

    def _apply(self, event: ProgressEvent) -> None:
        if event.status == ProgressStatus.DOWNLOADING:
            self.status_var.set("Baixando")
            if event.percent is not None:
                self.progress_var.set(event.percent)
            if event.eta_seconds is not None:
                self.eta_var.set(f"ETA: {event.eta_seconds}s")
        elif event.status == ProgressStatus.MERGING:
            self.status_var.set("Mesclando arquivos")
        elif event.status == ProgressStatus.POSTPROCESSING:
            self.status_var.set(event.message or "Pós-processando")
        elif event.status == ProgressStatus.FINISHED:
            self.status_var.set("Concluído")
            self.progress_var.set(100)
            self.eta_var.set("")
        elif event.status == ProgressStatus.ERROR:
            self.status_var.set(event.message or "Erro")

    def _done(self) -> None:
        self.busy = False
        self.queue_label.config(text=f"Fila: {self.queue.qsize()}")
        self._next()


def main() -> None:
    root = tk.Tk()
    RubethystDesktopApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
