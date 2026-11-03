#!/usr/bin/env python3
"""Instala para o usuário atual, sem sudo e sem alterar serviços/rede."""
import os
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
binary = root / 'dist' / 'Truco-da-Mesa'
if not binary.is_file():
    raise SystemExit('Gere o executável primeiro: python packaging/build_native.py')
base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share')))
install = base / 'truco-da-mesa'
install.mkdir(parents=True, exist_ok=True)
target = install / 'Truco-da-Mesa'
shutil.copy2(binary, target)
target.chmod(0o755)
shutil.copy2(root / 'packaging' / 'CREDITOS.txt', install)
icon = install / 'truco-da-mesa.png'
shutil.copy2(root / 'packaging' / 'truco-da-mesa.png', icon)
apps = base / 'applications'
apps.mkdir(parents=True, exist_ok=True)
launcher = apps / 'truco-da-mesa.desktop'
# Desktop Entry quoting escapes whitespace and reserved characters in Exec.
def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
launcher.write_text(f'''[Desktop Entry]
Type=Application
Version=1.0
Name=Truco da Mesa
GenericName=Truco paulista offline
Comment=Jogue contra bots ou com amigos na rede local, sem internet
Exec={quote(target)}
Icon={icon}
Terminal=false
Categories=Game;CardGame;
StartupNotify=true
StartupWMClass=Truco da Mesa
Actions=Fullscreen;

[Desktop Action Fullscreen]
Name=Jogar em tela cheia
Exec={quote(target)} --fullscreen
''', encoding='utf-8')
launcher.chmod(0o755)
if shutil.which('update-desktop-database'):
    subprocess.run(['update-desktop-database', str(apps)], check=False)
print(f'Instalado: {target}\nAtalho no menu: {launcher}')
