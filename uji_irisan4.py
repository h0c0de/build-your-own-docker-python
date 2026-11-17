# uji_irisan4.py — Bukti final Irisan 4: SEMUA isolasi dalam SATU
# perintah, diperiksa dari dalam dan dari host sekaligus.
# Satu container berjalan dengan hostname + overlay + batas memori
# + jaringan sendiri, mencetak laporannya; host memverifikasi
# setiap baris dan memastikan dirinya tidak ikut berubah.

import os
import socket
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wadah

gagal = []


def cek(nama, kondisi, detail=''):
    print(('PASS' if kondisi else 'FAIL'), nama, detail)
    if not kondisi:
        gagal.append(nama)


WADAH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wadah.py')
BUSYBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aset', 'busybox')

with tempfile.TemporaryDirectory() as d:
    rootfs = wadah.buat_rootfs(os.path.join(d, 'rootfs'), BUSYBOX)
    with open(os.path.join(rootfs, 'sambutan.txt'), 'w') as f:
        f.write('halo-dari-image')
    lap = os.path.join(d, 'lapisan')
    host_hostname = socket.gethostname()

    skrip = '; '.join([
        'echo HOSTNAME=$(hostname)',
        'echo PIDKU=$$',
        'echo SAMBUTAN=$(cat /sambutan.txt)',
        'ip link | grep -c eth0 || echo TANPA-ETH0',
        'ping -c 1 -W 2 127.0.0.1 >/dev/null && echo PING-OK',
        'hog memori 200 | tail -1',
        'echo jejak-container > /jejak.txt',
        'echo SELESAI-DALAM',
    ])
    p = subprocess.run(['python3', WADAH, '--hostname', 'finalku',
                        '--lapisan', lap, '--memori', '64',
                        'run', rootfs, '/bin/sh', '-c', skrip],
                       capture_output=True, text=True, timeout=120)
    out = p.stdout
    cek('container selesai dengan kode 0', p.returncode == 0,
        f'rc={p.returncode} {p.stderr.strip()[:100]}')
    cek('hostname sendiri', 'HOSTNAME=finalku' in out)
    cek('PID 1', 'PIDKU=1' in out)
    cek('isi image terbaca lewat overlay', 'SAMBUTAN=halo-dari-image' in out)
    cek('jaringan hanya loopback', 'TANPA-ETH0' in out and 'PING-OK' in out)
    cek('batas memori aktif BERSAMAAN dengan semua isolasi lain',
        'GAGAL-ALOKASI' in out, out.strip().split('\n')[-3] if out.strip() else '')
    cek('jejak tertulis di lapisan atas container',
        open(os.path.join(lap, 'atas', 'jejak.txt')).read().strip() == 'jejak-container')
    cek('image dasar tetap bersih', not os.path.exists(os.path.join(rootfs, 'jejak.txt')))
    cek('hostname host tidak berubah', socket.gethostname() == host_hostname)

print()
if gagal:
    print('GAGAL:', ', '.join(gagal))
    sys.exit(1)
print('SEMUA PASS — Irisan 4 terbukti: satu perintah, container terisolasi penuh.')
