from setuptools import setup

APP = ['app.py']
DATA_FILES = ['ui.html', 'icon.png']
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
    },
    'packages': ['backend'],
    'iconfile': 'icon.icns',
}

setup(
    name="dockdong",
    version="0.1.0",
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
