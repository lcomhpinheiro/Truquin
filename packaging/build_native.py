#!/usr/bin/env python3
"""Empacota o app Qt com Python, bibliotecas e assets locais."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
    '--name', 'Truco-da-Mesa', '--add-data', f'{ROOT / "static"}{os.pathsep}static',
    '--add-data', f'{ROOT / "packaging" / "CREDITOS.txt"}{os.pathsep}.',
    '--exclude-module', 'tkinter', '--exclude-module', 'PySide6.QtWebEngineCore',
    '--exclude-module', 'PySide6.QtWebEngineWidgets', '--exclude-module', 'PySide6.QtQml',
    '--exclude-module', 'PySide6.QtQuick', '--exclude-module', 'matplotlib',
    '--specpath', str(ROOT / 'build'), '--distpath', str(ROOT / 'dist'),
    '--workpath', str(ROOT / 'build' / 'pyinstaller'), str(ROOT / 'desktop.py')]
subprocess.run(command, check=True)
print(f'\nExecutável gerado: {ROOT / "dist" / "Truco-da-Mesa"}')
