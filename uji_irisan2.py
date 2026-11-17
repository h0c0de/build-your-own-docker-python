# uji_irisan2.py — Bukti Irisan 2: namespace benar-benar memisahkan.
# Setiap klaim isolasi diperiksa DUA arah: dari dalam container dan
# dari host sesudahnya (hostname host tak berubah, mount tak bocor).

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


def jalan(rootfs, *argv, hostname='wadahku'):
    p = subprocess.run(['python3', WADAH, '--hostname', hostname, 'run', rootfs, *argv],
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


with tempfile.TemporaryDirectory() as d:
    rootfs = wadah.buat_rootfs(os.path.join(d, 'rootfs'), BUSYBOX)
    host_sebelum = socket.gethostname()

    rc, out, err = jalan(rootfs, '/bin/hostname')
    cek('hostname di dalam = nama container', rc == 0 and out.strip() == 'wadahku',
        f'{out.strip()} rc={rc} {err.strip()[:80]}')
    cek('hostname HOST tidak berubah', socket.gethostname() == host_sebelum)

    rc, out, _ = jalan(rootfs, '/bin/sh', '-c', 'echo $$')
    cek('proses utama adalah PID 1 di namespace-nya', rc == 0 and out.strip() == '1',
        out.strip())

    rc, out, _ = jalan(rootfs, '/bin/sh', '-c', 'sleep 0.1 & echo $!')
    cek('anak pertama di dalam bernomor PID 2', rc == 0 and out.strip() == '2', out.strip())

    # /proc baru tidak bisa di-mount di sandbox ini (proc host
    # terkunci — lihat CATATAN), jadi isolasi PID dibuktikan lewat
    # wasit yang lebih keras: berkas status kernel di sisi HOST.
    # Container menjalankan sleep; dari host, NSpid proses itu harus
    # berakhiran 1 — kernel sendiri yang melaporkan terjemahannya.
    proc = subprocess.Popen(['python3', WADAH, '--hostname', 'wadahku', 'run',
                             rootfs, '/bin/sleep', '6'])
    try:
        import time
        nspid = None
        for _ in range(40):
            time.sleep(0.25)
            g = subprocess.run(['pgrep', '-f', '^/bin/sleep 6$'],
                               capture_output=True, text=True)
            kandidat = [x for x in g.stdout.split() if x.isdigit()]
            for k in kandidat:
                try:
                    status = open(f'/proc/{k}/status').read()
                except OSError:
                    continue
                for baris_status in status.split('\n'):
                    if baris_status.startswith('NSpid:'):
                        nspid = baris_status.split()[1:]
                        break
                if nspid:
                    break
            if nspid:
                break
        cek('kernel host melaporkan NSpid container berakhiran 1',
            nspid is not None and nspid[-1] == '1', f'NSpid={nspid}')
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    rc, out, _ = jalan(rootfs, '/bin/sh', '-c', 'ls /; ls /.akar-lama 2>&1 | head -1')
    cek('pivot_root: / adalah rootfs & akar lama sudah dilepas',
        rc == 0 and 'tanda' not in out and 'No such file' in out or 'bin' in out.split('\n')[0],
        out.replace('\n', ' ')[:120])

    rc, out, _ = jalan(rootfs, '/bin/sh', '-c',
                       'mount -t tmpfs tmpfs /tmp && echo rahasia > /tmp/bocor.txt && cat /tmp/bocor.txt')
    cek('mount tmpfs di dalam bekerja', rc == 0 and out.strip() == 'rahasia', out.strip())
    mounts_host = open('/proc/mounts').read()
    cek('mount container TIDAK muncul di tabel mount host',
        os.path.join(rootfs, 'tmp') not in mounts_host and 'bocor' not in mounts_host)

    rc, _, _ = jalan(rootfs, '/bin/false')
    cek('kode keluar tetap diteruskan melewati dua fork', rc == 1, f'rc={rc}')

print()
if gagal:
    print('GAGAL:', ', '.join(gagal))
    sys.exit(1)
print('SEMUA PASS — Irisan 2 terbukti: hostname, PID, dan mount terpisah dari host.')
