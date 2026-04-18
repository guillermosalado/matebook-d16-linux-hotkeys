#!/usr/bin/env python3
"""
Huawei MateBook D16 — Search Key Daemon
========================================
Diferencia las teclas F3/Búsqueda de F7/F9/F10 en Linux.

Problema: Todas mandan el mismo scancode (0xf7) por el teclado AT.
Solución: Monitorear ambos dispositivos simultáneamente.
  - F3/Búsqueda → solo evento en teclado AT (event2)
  - F7/F9/F10   → evento en teclado AT + evento en Huawei WMI (event11)

Dependencias: python3-evdev, keyd
"""

import evdev
import subprocess
import threading
import time
import os
import sys

# ─────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────

# Tiempo máximo (segundos) entre search_down y evento Huawei
# para considerar que es F7/F9/F10 y no F3/Búsqueda
HUAWEI_WINDOW = 0.05

# Cooldown entre activaciones para evitar doble disparo
COOLDOWN = 0.3

# Script a ejecutar al detectar F3/Búsqueda
SCRIPT_PATH = os.path.join(os.path.expanduser("~"), ".local/bin/toggle-launcher.sh")

# ─────────────────────────────────────────
# Estado compartido entre hilos
# ─────────────────────────────────────────

# Timestamp del último evento del driver Huawei WMI
huawei_event_time = 0.0

# Timestamp del último KEY_SEARCH DOWN
search_down_time = 0.0

# Timestamp de la última ejecución (para cooldown)
last_trigger = 0.0


# ─────────────────────────────────────────
# Búsqueda dinámica de dispositivos
# ─────────────────────────────────────────

def find_device(name: str):
    """
    Busca un dispositivo de input por nombre.
    Más portable que hardcodear /dev/input/eventN,
    ya que los números pueden cambiar entre reinicios.
    """
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            if name in dev.name:
                return dev
        except Exception:
            pass
    return None


# ─────────────────────────────────────────
# Hilo monitor del driver Huawei WMI
# ─────────────────────────────────────────

def watch_huawei(dev) -> None:
    """
    Monitorea el dispositivo Huawei WMI hotkeys en un hilo separado.
    Registra el timestamp de cualquier KEY_DOWN.

    F7  → KEY_MICMUTE (248)  → silencia micrófono (manejado por driver)
    F9  → KEY_WLAN    (238)  → toggle WiFi (manejado por driver)
    F10 → KEY_CONFIG  (171)  → abre configuración (manejado por driver)

    Estos eventos llegan casi simultáneamente con KEY_SEARCH de event2
    cuando se presiona F7/F9/F10, permitiendo identificarlas.
    """
    global huawei_event_time
    for event in dev.read_loop():
        if event.type == evdev.ecodes.EV_KEY and event.value == 1:
            huawei_event_time = time.time()


# ─────────────────────────────────────────
# Inicialización
# ─────────────────────────────────────────

huawei = find_device("Huawei WMI hotkeys")
keyboard = find_device("AT Translated Set 2 keyboard")

if not huawei or not keyboard:
    print("Error: dispositivos de input no encontrados.")
    print("Se requieren:")
    print("  - Huawei WMI hotkeys")
    print("  - AT Translated Set 2 keyboard")
    sys.exit(1)

# Iniciar hilo del driver Huawei
t = threading.Thread(target=watch_huawei, args=(huawei,), daemon=True)
t.start()


# ─────────────────────────────────────────
# Loop principal — teclado AT
# ─────────────────────────────────────────

for event in keyboard.read_loop():
    # Solo eventos de teclas
    if event.type != evdev.ecodes.EV_KEY:
        continue

    # Solo KEY_SEARCH (mapeado por hwdb desde scancode 0xf7)
    if event.code != evdev.ecodes.KEY_SEARCH:
        continue

    # KEY DOWN: registrar timestamp de inicio de pulsación
    if event.value == 1:
        search_down_time = time.time()

    # KEY UP: decidir si ejecutar o ignorar
    elif event.value == 0:
        # Si Huawei WMI emitió un evento entre el DOWN y el UP,
        # es F7/F9/F10 → ignorar.
        # F3/Búsqueda no generan eventos en Huawei WMI.
        if huawei_event_time > 0 and \
           0 <= (huawei_event_time - search_down_time) < HUAWEI_WINDOW:
            continue

        # Cooldown para evitar múltiples ejecuciones
        now = time.time()
        if now - last_trigger > COOLDOWN:
            last_trigger = now
            subprocess.Popen(['bash', SCRIPT_PATH])