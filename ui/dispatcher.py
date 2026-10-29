"""
Despachador de tareas seguro para hilos (Thread-Safe UI Dispatcher).
Garantiza compatibilidad total con Python 3.13 resolviendo la excepción
'RuntimeError: main thread is not in main loop' al interactuar con Tkinter desde hilos secundarios.
"""

import queue
import threading
from typing import Any, Callable

_task_queue: queue.Queue = queue.Queue()
_main_thread_id: int = threading.get_ident()


def set_main_thread() -> None:
    """Registra el identificador del hilo principal de la interfaz."""
    global _main_thread_id
    _main_thread_id = threading.get_ident()


def is_main_thread() -> bool:
    """Comprueba si el hilo en ejecución es el principal de la GUI."""
    return threading.get_ident() == _main_thread_id


def dispatch_to_main(task: Callable[[], Any]) -> None:
    """
    Encola una función para que sea ejecutada por el hilo principal de la interfaz gráfica.
    Es 100% seguro invocarla desde cualquier hilo secundario.
    """
    _task_queue.put(task)


def init_dispatcher(root_widget, poll_interval_ms: int = 60) -> None:
    """
    Inicia el bucle de consumo de la cola en el hilo principal de la ventana.
    Debe llamarse desde el __init__ de MainWindow.
    """
    set_main_thread()

    def _poll():
        try:
            if not root_widget.winfo_exists():
                return
        except Exception:
            return

        try:
            # Procesar todas las tareas pendientes en la cola
            while True:
                task = _task_queue.get_nowait()
                try:
                    if root_widget.winfo_exists():
                        task()
                except Exception as e:
                    # Silenciar errores si la ventana se cerró durante la ejecución
                    pass
        except queue.Empty:
            pass

        try:
            if root_widget.winfo_exists():
                root_widget.after(poll_interval_ms, _poll)
        except Exception:
            pass

    # Iniciar la primera comprobación en el hilo principal
    root_widget.after(poll_interval_ms, _poll)
