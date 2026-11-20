from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess


FILMCRAFT_CANDIDATES = (
    Path(os.environ.get("DEX_FILMCRAFT_CLI", "")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "FilmCraft/filmcraft-cli.exe",
    Path(shutil.which("filmcraft-cli") or ""),
)
PHOTOCRAFT_CANDIDATES = (
    Path(os.environ.get("DEX_PHOTOCRAFT_CLI", "")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PhotoCraft/photocraft-cli.exe",
    Path(shutil.which("photocraft-cli") or ""),
)


def _first_file(candidates: tuple[Path, ...]) -> Path | None:
    return next((path for path in candidates if str(path) and path.is_file()), None)


def filmcraft_cli() -> Path | None:
    return _first_file(FILMCRAFT_CANDIDATES)


def photocraft_cli() -> Path | None:
    return _first_file(PHOTOCRAFT_CANDIDATES)


def _environment(home: Path) -> dict[str, str]:
    allowed = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP")
    environment = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    environment.update({"HOME": str(home), "USERPROFILE": str(home)})
    return environment


def _run_json(command: list[str], home: Path, timeout: int = 120) -> dict:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_environment(home),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or f"A ferramenta terminou com código {completed.returncode}.")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("A ferramenta não retornou JSON válido.") from error


def versions(home: Path) -> dict[str, dict[str, str | bool | None]]:
    result: dict[str, dict[str, str | bool | None]] = {}
    for name, executable in (("filmcraft", filmcraft_cli()), ("photocraft", photocraft_cli())):
        version = None
        if executable:
            completed = subprocess.run(
                [str(executable), "--version"],
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                env=_environment(home),
            )
            if completed.returncode == 0:
                version = completed.stdout.strip()
        result[name] = {"available": bool(executable), "path": str(executable) if executable else None, "version": version}
    return result


def probe_media(source: Path, home: Path) -> dict:
    executable = filmcraft_cli()
    if not executable:
        raise FileNotFoundError("filmcraft-cli não foi encontrado.")
    return _run_json([str(executable), "probe", str(source)], home)


def inspect_image(source: Path, home: Path, detail: bool = False) -> dict:
    executable = photocraft_cli()
    if not executable:
        raise FileNotFoundError("photocraft-cli não foi encontrado.")
    command = [str(executable), "info", str(source), "--compact"]
    if detail:
        command.append("--detail")
    return _run_json(command, home)
