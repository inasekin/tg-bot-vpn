import subprocess
import logging

logger = logging.getLogger(__name__)


def add_peer_to_server(public_key, allowed_ip):
    """
    Добавить пира на WireGuard сервер

    Args:
        public_key: Публичный ключ клиента
        allowed_ip: IP адрес клиента (например: 10.0.0.2)

    Returns:
        bool: True если успешно
    """
    try:
        # Добавляем пира через wg команду
        cmd = [
            'wg', 'set', 'wg0',
            'peer', public_key,
            'allowed-ips', f'{allowed_ip}/24'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Добавлен пир {public_key[:8]}... с IP {allowed_ip}")

        # Сохраняем конфигурацию
        subprocess.run(['wg-quick', 'save', 'wg0'], check=True)

        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка с добавлением: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.warning("WireGuard не детектится")
        return False


def remove_peer_from_server(public_key):
    """
    Удалить пира с WireGuard сервера

    Args:
        public_key: Публичный ключ клиента

    Returns:
        bool: True если успешно
    """
    try:
        cmd = ['wg', 'set', 'wg0', 'peer', public_key, 'remove']

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Удаляем peer {public_key[:8]}...")

        subprocess.run(['wg-quick', 'save', 'wg0'], check=True)

        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка с удалением peer: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.warning("WireGuard не детектится")
        return False