import sys
sys.setrecursionlimit(10000)
from setuptools import setup

APP = ['app.py']
DATA_FILES = ['ui.html', 'icon.png']
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,
    },
    'includes': ['backend'],
    'iconfile': 'icon.icns',
    'excludes': ['zmq', 'matplotlib', 'numpy', 'pandas', 'PyQt5', 'PySide6', 'IPython', 'pytest', 'black'],
}

setup(
    name="dockdong",
    version="0.1.0",
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
