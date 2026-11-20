from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import sounddevice as sd
import soundfile as sf


SCRIPT = """Hoje vamos analisar cinco acontecimentos importantes da semana. Eu vou explicar o que aconteceu, por que isso importa e o que pode mudar daqui para frente.

Em uma notícia séria, eu falo com calma, clareza e firmeza, sem exagerar e sem apressar as palavras. Quando a notícia é positiva, minha voz fica mais leve, próxima e naturalmente animada.

Os dados precisam ser exatos: vinte e cinco por cento, três vírgula sete milhões e dezoito de novembro de dois mil e vinte e seis. Nomes, lugares e termos estrangeiros devem continuar fáceis de entender.

Now I will read two sentences in English. This reference helps the system preserve my natural rhythm, pronunciation, and tone. The final narration should sound clear, human, and comfortable to listen to."""


def preferred_input() -> tuple[int, dict]:
    inputs = [
        (index, dict(device))
        for index, device in enumerate(sd.query_devices())
        if int(device.get("max_input_channels", 0)) > 0
    ]
    if not inputs:
        raise RuntimeError("Nenhum microfone foi encontrado.")
    fuxi = [item for item in inputs if "fuxi-h3" in item[1]["name"].casefold()]
    return (fuxi or inputs)[0]


class Recorder(tk.Tk):
    def __init__(self, output: Path) -> None:
        super().__init__()
        self.output = output
        self.device_index, self.device = preferred_input()
        self.rate = int(self.device["default_samplerate"])
        self.stream: sd.InputStream | None = None
        self.frames: list[np.ndarray] = []
        self.started_at = 0.0
        self.title("Gravar minha voz para o canal dark")
        self.geometry("900x720")
        self.minsize(720, 580)

        ttk.Label(self, text="Referência da sua voz", font=("Segoe UI", 18, "bold")).pack(
            anchor="w", padx=24, pady=(20, 4)
        )
        ttk.Label(
            self,
            text=f"Microfone: {self.device['name']}  |  {self.rate} Hz  |  tudo fica local",
        ).pack(anchor="w", padx=24, pady=(0, 12))
        ttk.Label(
            self,
            text="Leia naturalmente. Faça as pausas dos parágrafos; não force emoção nem imite locutor.",
        ).pack(anchor="w", padx=24, pady=(0, 8))

        text = tk.Text(self, wrap="word", font=("Segoe UI", 13), padx=16, pady=14, height=22)
        text.insert("1.0", SCRIPT)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=24, pady=(0, 10))
        self.record_button = ttk.Button(controls, text="Gravar", command=self.start_recording)
        self.record_button.pack(side="left")
        self.stop_button = ttk.Button(
            controls, text="Parar e salvar", command=self.stop_recording, state="disabled"
        )
        self.stop_button.pack(side="left", padx=10)
        self.play_button = ttk.Button(
            controls, text="Ouvir gravação", command=self.play_recording, state="disabled"
        )
        self.play_button.pack(side="left")
        self.timer = ttk.Label(controls, text="00:00", font=("Segoe UI", 12, "bold"))
        self.timer.pack(side="right")
        self.status = ttk.Label(self, text="Clique em Gravar quando estiver pronto.")
        self.status.pack(anchor="w", padx=24, pady=(0, 18))
        self.after(200, self.tick)

    def capture(self, data, _frames, _time_info, status) -> None:
        if status:
            self.after(0, lambda: self.status.configure(text=f"Aviso do microfone: {status}"))
        self.frames.append(data[:, :1].copy())

    def start_recording(self) -> None:
        self.frames.clear()
        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                samplerate=self.rate,
                channels=1,
                dtype="float32",
                callback=self.capture,
            )
            self.stream.start()
        except Exception as error:
            self.stream = None
            messagebox.showerror("Não foi possível gravar", str(error))
            return
        self.started_at = time.monotonic()
        self.record_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.play_button.configure(state="disabled")
        self.status.configure(text="Gravando pelo Fuxi-H3… leia o texto completo.")

    def stop_recording(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if not self.frames:
            messagebox.showwarning("Gravação vazia", "Nenhum áudio foi capturado.")
            self.reset_controls()
            return
        audio = np.concatenate(self.frames, axis=0)
        duration = len(audio) / self.rate
        if duration < 20:
            messagebox.showwarning(
                "Gravação muito curta",
                "A gravação foi salva, mas leia o texto inteiro para obter uma referência melhor.",
            )
        self.output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(self.output, audio, self.rate, subtype="PCM_24")
        metadata = {
            "device": self.device["name"],
            "sample_rate": self.rate,
            "duration_seconds": round(duration, 2),
            "consent": "owner-authorized-local-voice-clone",
            "languages": ["pt-BR", "en"],
            "reference_audio": str(self.output),
        }
        self.output.with_suffix(".json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.record_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.play_button.configure(state="normal")
        self.status.configure(text=f"Salvo: {self.output}  ({duration:.1f} segundos)")

    def reset_controls(self) -> None:
        self.record_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status.configure(text="Pronto para tentar novamente.")

    def play_recording(self) -> None:
        if self.output.is_file():
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(New-Object Media.SoundPlayer '{self.output}').PlaySync()",
                ]
            )

    def tick(self) -> None:
        if self.stream is not None:
            elapsed = int(time.monotonic() - self.started_at)
            self.timer.configure(text=f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        self.after(200, self.tick)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Recorder(Path(args.output).expanduser().resolve()).mainloop()


if __name__ == "__main__":
    main()
