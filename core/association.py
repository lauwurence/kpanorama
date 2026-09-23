################################################################################
## File Association

import os
import sys
import ctypes

def register_kpp_file_association():
    if sys.platform != "win32":
        return

    import winreg

    try:
        if getattr(sys, "frozen", False):
            # Если программа собрана в .exe
            app_path = sys.executable
            command = f'"{app_path}" "%1"'

        else:
            # Если запускаем .py напрямую
            app_path = os.path.abspath(sys.argv[0])

            pythonw = os.path.join(
                os.path.dirname(sys.executable),
                "pythonw.exe",
            )

            command = (
                f'"{pythonw}" '
                f'"{app_path}" "%1"'
            )

        # .kpp -> kPanorama.Project
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\.kpp",
        ) as key:
            winreg.SetValueEx(
                key,
                "",
                0,
                winreg.REG_SZ,
                "kPanorama.Project",
            )

        # Описание типа файла
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\kPanorama.Project",
        ) as key:
            winreg.SetValueEx(
                key,
                "",
                0,
                winreg.REG_SZ,
                "kPanorama Project",
            )

        # Команда открытия
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\kPanorama.Project\shell\open\command",
        ) as key:
            winreg.SetValueEx(
                key,
                "",
                0,
                winreg.REG_SZ,
                command,
            )

        ctypes.windll.shell32.SHChangeNotify(
            0x08000000,
            0x0000,
            None,
            None,
        )

        print("Ассоциация .kpp зарегистрирована")

    except Exception as e:
        print(
            f"Не удалось зарегистрировать .kpp: {e}"
        )

    icon_path = os.path.abspath("icons/kpp.ico")

    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Classes\kPanorama.Project\DefaultIcon",
    ) as key:
        winreg.SetValueEx(
            key,
            "",
            0,
            winreg.REG_SZ,
            icon_path,
        )
