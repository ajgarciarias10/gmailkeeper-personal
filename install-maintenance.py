#!/usr/bin/env python3
"""Instala, consulta o desactiva el temporizador Linux de un perfil personal."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import gmailkeeper


def unit_argument(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'status', 'remove'], nargs='?', default='install')
    parser.add_argument('--config', type=Path, default=gmailkeeper.DEFAULT_CONFIG)
    parser.add_argument('--interval', type=int, default=3, help='Minutos entre revisiones, de 1 a 60')
    parser.add_argument('--run-now', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Este instalador usa systemd en Linux. Consulta docs/AUTOMATIZACION.md para macOS y Windows.')
    if not 1 <= args.interval <= 60:
        parser.error('--interval debe estar entre 1 y 60')
    config_path = args.config.expanduser().resolve()
    gmailkeeper.configure(config_path)
    identity = str(gmailkeeper.STATE_DIR) + gmailkeeper.ACCOUNT
    profile = hashlib.sha256(identity.encode()).hexdigest()[:12]
    service_name = 'gmailkeeper-' + profile
    timer_name = service_name + '.timer'
    if args.command == 'status':
        subprocess.run(['systemctl', '--user', 'list-timers', timer_name, '--all', '--no-pager'], check=True)
        subprocess.run(['systemctl', '--user', 'show', service_name + '.service', '--property=Result', '--property=ExecMainStatus'], check=True)
        subprocess.run(['journalctl', '--user', '--unit=' + service_name + '.service', '-n', '10', '--no-pager'], check=True)
        return
    if args.command == 'remove':
        subprocess.run(['systemctl', '--user', 'disable', '--now', timer_name], check=True)
        print('Temporizador desactivado. Los filtros nativos de Gmail siguen activos.')
        print('Para retirarlos: python gmailkeeper.py remove-filters --config', config_path, '--apply')
        return
    source = Path(__file__).resolve().parent
    installation = Path.home() / '.local/share/gmailkeeper' / profile
    units = Path.home() / '.config/systemd/user'
    installation.mkdir(parents=True, exist_ok=True, mode=0o700)
    units.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / 'gmailkeeper.py', installation / 'gmailkeeper.py')
    (installation / 'gmailkeeper.py').chmod(0o600)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if gmailkeeper.BRANDS_FILE:
        shutil.copyfile(gmailkeeper.BRANDS_FILE, installation / 'brands.json')
        (installation / 'brands.json').chmod(0o600)
        config['brands_file'] = str(installation / 'brands.json')
    config['credentials'] = str(gmailkeeper.CREDENTIALS)
    config['state_dir'] = str(gmailkeeper.STATE_DIR)
    installed_config = installation / 'config.json'
    gmailkeeper.save(installed_config, config)
    interpreter = Path(sys.executable).resolve()
    service = f'''[Unit]
Description=GmailKeeper personal mail maintenance

[Service]
Type=oneshot
ExecStart={unit_argument(interpreter)} {unit_argument(installation / 'gmailkeeper.py')} sync --config {unit_argument(installed_config)} --limit 200 --apply
Environment=PYTHONUNBUFFERED=1
UMask=0077
TimeoutStartSec=15min
'''
    timer = f'''[Unit]
Description=GmailKeeper every {args.interval} minutes

[Timer]
OnCalendar=*:0/{args.interval}
Persistent=true
RandomizedDelaySec=10
Unit={service_name}.service

[Install]
WantedBy=timers.target
'''
    (units / (service_name + '.service')).write_text(service, encoding='utf-8')
    (units / timer_name).write_text(timer, encoding='utf-8')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', timer_name], check=True)
    print('Instalación:', installation)
    print('Temporizador:', timer_name)
    print('Tras editar tu configuración, repite install para actualizar la copia instalada.')
    if args.run_now:
        subprocess.run(['systemctl', '--user', 'start', service_name + '.service'], check=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        print('Error:', error)
        raise SystemExit(1)
