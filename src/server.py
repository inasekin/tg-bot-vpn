import subprocess
import logging

from config import ServerConfig

logger = logging.getLogger(__name__)

SSH_TIMEOUT = 15


def _build_command(server: ServerConfig, remote_args: list) -> list:
    """
    Строит итоговую команду для запуска: локально либо через SSH на удалённый сервер.
    remote_args — список аргументов команды, которая должна выполниться НА сервере.
    """
    if not server.is_remote:
        return remote_args

    if not server.ssh_key_path:
        raise RuntimeError(
            f"Для удалённого сервера '{server.key}' не задан WG_SERVER_SSH_KEY_{server.key.upper()}"
        )

    remote_cmd = " ".join(remote_args)
    return [
        "ssh",
        "-i",
        server.ssh_key_path,
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={SSH_TIMEOUT}",
        f"{server.ssh_user}@{server.ssh_host}",
        remote_cmd,
    ]


def _run(server: ServerConfig, remote_args: list, label: str) -> bool:
    cmd = _build_command(server, remote_args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=SSH_TIMEOUT
        )
        logger.info(f"[{server.key}] {label}: OK ({result.stdout.strip()[:200]})")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[{server.key}] {label}: ошибка — {e.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"[{server.key}] {label}: таймаут выполнения команды")
        return False
    except FileNotFoundError:
        logger.warning(f"[{server.key}] {label}: команда не найдена (awg/ssh не установлен?)")
        return False
    except RuntimeError as e:
        logger.error(f"[{server.key}] {label}: {e}")
        return False


def add_peer_to_server(server: ServerConfig, public_key: str, allowed_ip: str) -> bool:
    """
    Добавить пира на AmneziaWG сервер (локально или удалённо по SSH).
    """
    set_args = [
        "awg",
        "set",
        server.interface,
        "peer",
        public_key,
        "allowed-ips",
        f"{allowed_ip}/32",
    ]
    if not _run(server, set_args, "добавление пира"):
        return False

    save_args = ["awg-quick", "save", server.interface]
    return _run(server, save_args, "сохранение конфига")


def remove_peer_from_server(server: ServerConfig, public_key: str) -> bool:
    """
    Удалить пира с AmneziaWG сервера (локально или удалённо по SSH).
    """
    remove_args = ["awg", "set", server.interface, "peer", public_key, "remove"]
    if not _run(server, remove_args, "удаление пира"):
        return False

    save_args = ["awg-quick", "save", server.interface]
    return _run(server, save_args, "сохранение конфига")