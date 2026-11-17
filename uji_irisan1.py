# uji_irisan1.py — Bukti Irisan 1: fork/exec + chroot benar-benar
# mengurung. Wasitnya adalah sistem berkas host itu sendiri: dari
# dalam container, dunia harus berisi rootfs saja; tulisan harus
# mendarat di rootfs, bukan di host.

import os
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


def jalan(rootfs, *argv):
    p = subprocess.run(['python3', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wadah.py'),
                        'run', rootfs, *argv],
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


BUSYBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aset', 'busybox')

with tempfile.TemporaryDirectory() as d:
    rootfs = wadah.buat_rootfs(os.path.join(d, 'rootfs'), BUSYBOX)
    with open(os.path.join(rootfs, 'tanda.txt'), 'w') as f:
        f.write('milik-rootfs')

    rc, out, _ = jalan(rootfs, '/bin/sh', '-c', 'ls /')
    cek('ls / di dalam = isi rootfs saja',
        rc == 0 and 'tanda.txt' in out and 'bin' in out and 'home' not in out, out.replace('\n', ' '))
    rc, out, _ = jalan(rootfs, '/bin/cat', '/tanda.txt')
    cek('berkas tanda rootfs terbaca', rc == 0 and out.strip() == 'milik-rootfs')
    rc, out, _ = jalan(rootfs, '/bin/cat', '/etc/hostname')
    cek('berkas host TIDAK terjangkau dari dalam', rc != 0, f'rc={rc}')
    rc, out, _ = jalan(rootfs, '/bin/sh', '-c', 'echo halo > /tmp/dari-dalam.txt; echo $$')
    cek('perintah dalam container berjalan', rc == 0 and out.strip().isdigit(), out.strip())
    cek('tulisan mendarat DI ROOTFS (terlihat dari host)',
        open(os.path.join(rootfs, 'tmp', 'dari-dalam.txt')).read().strip() == 'halo')
    cek('tulisan TIDAK bocor ke /tmp host',
        not os.path.exists('/tmp/dari-dalam.txt'))
    rc, _, _ = jalan(rootfs, '/bin/false')
    cek('kode keluar perintah diteruskan (false -> 1)', rc == 1, f'rc={rc}')
    rc, out, _ = jalan(rootfs, '/bin/id', '-u')
    cek('di dalam container kita uid 0 (root semu userns)',
        rc == 0 and out.strip() == '0', out.strip())

print()
if gagal:
    print('GAGAL:', ', '.join(gagal))
    sys.exit(1)
print('SEMUA PASS — Irisan 1 terbukti: proses terkurung chroot di rootfs-nya sendiri.')
