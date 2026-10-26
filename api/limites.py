"""Limitador de peticiones en memoria (ventana deslizante por IP).

Suficiente para un único contenedor de backend. Si en el futuro se usan
varias réplicas, debe moverse a un almacén compartido (por ejemplo Redis).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_lock = threading.Lock()
_registros = defaultdict(deque)


def verificar_limite(clave, maximo, ventana_segundos):
    """Lanza 429 si `clave` superó `maximo` peticiones en la ventana."""
    momento = time.monotonic()
    with _lock:
        cola = _registros[clave]
        while cola and momento - cola[0] > ventana_segundos:
            cola.popleft()
        if len(cola) >= maximo:
            espera = int(ventana_segundos - (momento - cola[0])) + 1
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos. Espere unos minutos e intente de nuevo.",
                headers={"Retry-After": str(max(espera, 1))},
            )
        cola.append(momento)


def reiniciar():
    """Solo para pruebas."""
    with _lock:
        _registros.clear()
