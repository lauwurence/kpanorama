
import os
from PyQt6.QtGui import QIcon

BASE_DIR = None
ICON_DIR = None

def icon(name):
    return QIcon(os.path.join(ICON_DIR, name))
