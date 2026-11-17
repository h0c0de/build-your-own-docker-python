# uji_irisan3.py — Bukti Irisan 3: jaringan sendiri, batas yang
# benar-benar menahan, dan lapisan tulis overlay.
# cgroup dicoba lebih dulu di probe (mount cgroup2 di userns ->
# EPERM): jalurnya tertutup di sandbox ini, jadi batas memakai
# rlimit — ditegakkan kernel, diwarisi anak, dan dibuktikan dengan
# beban sungguhan (hog), bukan dengan membaca berkas konfigurasi.

import http.client
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wadah

gagal = []


def cek(nama, kondisi, detail=''):
    print(('PASS' if kondisi else 'FAIL'), nama, detail)
    if not kondisi:
        gagal.append(nama)


WADAH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wadah.py')
BUSYBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aset', 'busybox')


def jalan(rootfs, *argv, ekstra=()):
    p = subprocess.run(['python3', WADAH, *ekstra, 'run', rootfs, *argv],
                       capture_output=True, text=True, timeout=90)
    return p.returncode, p.stdout, p.stderr


with tempfile.TemporaryDirectory() as d:
    rootfs = wadah.buat_rootfs(os.path.join(d, 'rootfs'), BUSYBOX)

    # --- jaringan ---
    rc, out, _ = jalan(rootfs, '/bin/ip', 'link')
    cek('di dalam hanya ada loopback', rc == 0 and 'lo:' in out and 'eth0' not in out,
        out.replace('\n', ' ')[:100])
    rc, out, _ = jalan(rootfs, '/bin/ping', '-c', '1', '-W', '2', '127.0.0.1')
    cek('loopback hidup: ping 127.0.0.1 dijawab', rc == 0 and 'bytes from' in out,
        out.strip().split('\n')[0][:60] if out.strip() else f'rc={rc}')

    # port yang sama, dua dunia: container melayani 18099 di dunianya;
    # host harus tetap bisa memakai 18099 dan yang menjawab di host
    # adalah server HOST, bukan container.
    with open(os.path.join(rootfs, 'index.html'), 'w') as f:
        f.write('DARI-CONTAINER')
    kont = subprocess.Popen(['python3', WADAH, 'run', rootfs, '/bin/sh', '-c',
                             'httpd -p 18099; sleep 5'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(('127.0.0.1', 18099))
            bind_ok = True
        except OSError:
            bind_ok = False
        cek('host tetap bisa bind port 18099 saat container memakainya',
            bind_ok)
        if bind_ok:
            srv.listen(1)

            def layani():
                conn, _ = srv.accept()
                conn.recv(4096)  # baca request dulu; menutup soket
                # dengan data belum terbaca membuat kernel mengirim
                # RST yang membuang jawaban kita sendiri.
                conn.sendall(b'HTTP/1.0 200 OK\r\nContent-Length: 9\r\n\r\nDARI-HOST')
                conn.close()
            threading.Thread(target=layani, daemon=True).start()
            c = http.client.HTTPConnection('127.0.0.1', 18099, timeout=5)
            c.request('GET', '/')
            badan = c.getresponse().read().decode()
            cek('yang menjawab di host adalah server HOST', badan == 'DARI-HOST', badan)
            srv.close()
    finally:
        kont.terminate()
        kont.wait(timeout=10)

    # --- batas memori (hog beban sungguhan) ---
    rc, out, _ = jalan(rootfs, '/bin/hog', 'memori', '96')
    cek('tanpa batas: hog menyelesaikan 96 MB', rc == 0 and 'SELESAI' in out,
        out.strip().split('\n')[-1] if out.strip() else f'rc={rc}')
    rc, out, _ = jalan(rootfs, '/bin/hog', 'memori', '200', ekstra=('--memori', '64'))
    cek('batas 64 MB menahan hog 200 MB (gagal alokasi, bukan selesai)',
        rc == 3 and 'GAGAL-ALOKASI' in out and 'SELESAI' not in out,
        f'rc={rc} {out.strip().splitlines()[-1] if out.strip() else ""}')

    # --- batas CPU ---
    t0 = time.time()
    rc, out, _ = jalan(rootfs, '/bin/hog', 'cpu', ekstra=('--cpu', '1'))
    durasi = time.time() - t0
    cek('batas CPU 1 detik membunuh pemutar abadi',
        rc == 137 and durasi < 6, f'rc={rc} durasi={durasi:.1f}s')

    # --- overlay (Level 04) ---
    with open(os.path.join(rootfs, 'dari-base.txt'), 'w') as f:
        f.write('dasar')
    lap = os.path.join(d, 'lapisan')
    rc, out, _ = jalan(rootfs, '/bin/sh', '-c',
                       'cat /dari-base.txt; echo tulisanku > /baru.txt',
                       ekstra=('--lapisan', lap))
    cek('overlay: isi dasar terbaca dari dalam', rc == 0 and 'dasar' in out, out.strip())
    cek('tulisan container mendarat di LAPISAN ATAS',
        open(os.path.join(lap, 'atas', 'baru.txt')).read().strip() == 'tulisanku')
    cek('rootfs dasar TIDAK ikut tertulis (tetap bersih)',
        not os.path.exists(os.path.join(rootfs, 'baru.txt')))
    rc, out, _ = jalan(rootfs, '/bin/cat', '/baru.txt', ekstra=('--lapisan', lap))
    cek('container kedua melihat lapisan yang sama (bertahan)',
        rc == 0 and out.strip() == 'tulisanku', out.strip())

print()
if gagal:
    print('GAGAL:', ', '.join(gagal))
    sys.exit(1)
print('SEMUA PASS — Irisan 3 terbukti: jaringan terpisah, batas menahan, overlay menulis di atas.')
