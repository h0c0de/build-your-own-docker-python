"""wadah — container runtime dari nol, mengikuti workshop rubber-docker
(Fewbytes): "Rebuild Docker from Scratch".

Irisan 1 (Level 00 fork/exec + 01 chroot image), dengan adaptasi
rootless: proses anak lebih dulu masuk user namespace (menjadi
"root" di dalam dunianya sendiri, memetakan uid kita di luar),
baru kemudian chroot ke rootfs. Syscall yang tak disediakan
pustaka standar dipanggil lewat ctypes ke libc — pengganti modul
C 'linux' milik workshop, semantik syscall-nya sama.
"""

import ctypes
import os
import resource
import struct
import sys

libc = ctypes.CDLL('libc.so.6', use_errno=True)

CLONE_NEWUSER = 0x10000000
CLONE_NEWNS = 0x00020000
CLONE_NEWUTS = 0x04000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000

MS_REC = 16384
MS_PRIVATE = 262144
MS_BIND = 4096
MS_NOSUID = 2
MS_NODEV = 4
MS_NOEXEC = 8
MNT_DETACH = 2


def _periksa(hasil, nama):
    if hasil != 0:
        e = ctypes.get_errno()
        raise OSError(e, f'{nama} gagal: {os.strerror(e)}')
    return hasil


def unshare(flags):
    return _periksa(libc.unshare(flags), 'unshare')


def _tulis(path, isi):
    with open(path, 'w') as f:
        f.write(isi)


def masuk_user_namespace():
    """Jadi root semu: uid 0 di dalam, uid kita di luar.
    Urutan wajib: unshare -> setgroups=deny -> gid_map -> uid_map."""
    uid, gid = os.getuid(), os.getgid()
    unshare(CLONE_NEWUSER)
    try:
        _tulis('/proc/self/setgroups', 'deny')
    except FileNotFoundError:
        pass
    _tulis('/proc/self/gid_map', f'0 {gid} 1')
    _tulis('/proc/self/uid_map', f'0 {uid} 1')
    # Sesudah setgroups=deny, syscall setgroups memang DILARANG di
    # namespace ini (itu gunanya deny) — jangan dipanggil; setgid
    # dan setuid ke id terpetakan yang diizinkan.
    os.setgid(0)
    os.setuid(0)


def buat_rootfs(tujuan, busybox):
    """Rootfs busybox minimal: satu biner statis + symlink applet."""
    os.makedirs(os.path.join(tujuan, 'bin'), exist_ok=True)
    os.makedirs(os.path.join(tujuan, 'dev'), exist_ok=True)
    os.makedirs(os.path.join(tujuan, 'etc'), exist_ok=True)
    os.makedirs(os.path.join(tujuan, 'proc'), exist_ok=True)
    os.makedirs(os.path.join(tujuan, 'tmp'), exist_ok=True)
    target = os.path.join(tujuan, 'bin', 'busybox')
    if not os.path.exists(target):
        with open(busybox, 'rb') as a, open(target, 'wb') as b:
            b.write(a.read())
        os.chmod(target, 0o755)
    for applet in ('sh', 'ls', 'cat', 'echo', 'pwd', 'hostname', 'ps',
                   'mount', 'umount', 'sleep', 'touch', 'mkdir', 'rm',
                   'id', 'uname', 'free', 'head', 'grep', 'true', 'false',
                   'ip', 'ifconfig', 'ping', 'nc', 'httpd', 'tail', 'wc',
                   'env', 'whoami', 'df', 'du', 'sort', 'uniq', 'xargs'):
        link = os.path.join(tujuan, 'bin', applet)
        if not os.path.exists(link):
            os.symlink('busybox', link)
    hog = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aset', 'hog')
    if os.path.exists(hog) and not os.path.exists(os.path.join(tujuan, 'bin', 'hog')):
        with open(hog, 'rb') as a, open(os.path.join(tujuan, 'bin', 'hog'), 'wb') as b:
            b.write(a.read())
        os.chmod(os.path.join(tujuan, 'bin', 'hog'), 0o755)
    return tujuan


def mount(sumber, target, fstype=None, flags=0, data=None):
    hasil = libc.mount(
        sumber.encode() if sumber else None,
        target.encode(),
        fstype.encode() if fstype else None,
        flags,
        data.encode() if data else None)
    return _periksa(hasil, f'mount {target}')


def umount2(target, flags=0):
    return _periksa(libc.umount2(target.encode(), flags), f'umount2 {target}')


def pivot_root(baru, lama):
    hasil = libc.pivot_root(baru.encode(), lama.encode())
    return _periksa(hasil, 'pivot_root')


def sethostname(nama):
    b = nama.encode()
    return _periksa(libc.sethostname(b, len(b)), 'sethostname')


def _keluar_dari(status):
    kode = os.waitstatus_to_exitcode(status)
    return kode if kode >= 0 else 128 - kode


SIOCSIFFLAGS = 0x8914
IFF_UP = 0x1
IFF_RUNNING = 0x40


def nyalakan_loopback():
    """Net namespace baru hanya punya lo, dan ia mati. Nyalakan via
    ioctl SIOCSIFFLAGS — kita CAP_NET_ADMIN atas namespace milik
    userns kita sendiri."""
    import socket as _s
    sock = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
    try:
        ifreq = struct.pack('16sh', b'lo', IFF_UP | IFF_RUNNING)
        import fcntl
        fcntl.ioctl(sock, SIOCSIFFLAGS, ifreq)
    finally:
        sock.close()


def terapkan_batas(batas_memori_mb, batas_cpu_detik):
    """Batas sumber daya (Level 08/09). Jalur cgroup tertutup di
    sandbox ini — mount cgroup2 di dalam userns ditolak EPERM,
    terbukti di probe Irisan 3 — jadi mekanismenya rlimit, yang
    diwarisi anak dan ditegakkan kernel per proses. Selisih dari
    workshop dicatat terbuka di CATATAN."""
    if batas_memori_mb:
        b = batas_memori_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (b, b))
    if batas_cpu_detik:
        resource.setrlimit(resource.RLIMIT_CPU,
                           (batas_cpu_detik, batas_cpu_detik))


def _proses_utama(rootfs, argv, hostname, lapisan=None,
                  batas_memori_mb=None, batas_cpu_detik=None):
    """Berjalan sebagai PID 1 di PID namespace baru (Level 02/03/05/06):
    hostname sendiri, mount privat, pivot_root ke rootfs, /proc baru."""
    sethostname(hostname)
    nyalakan_loopback()
    # Cegah mount kita merambat keluar (dan sebaliknya).
    mount('', '/', None, MS_REC | MS_PRIVATE)
    # Rootfs sungguhan butuh simpul /dev dasar. mknod dari userns
    # ditolak di berkas sistem milik namespace induk, jadi keempat
    # perangkat aman (null, zero, urandom, console) di-bind-mount
    # dari host — pola yang sama yang dipakai runtime rootless.
    for nama in ('null', 'zero', 'urandom', 'console'):
        target = os.path.join(rootfs, 'dev', nama)
        if not os.path.exists(target):
            open(target, 'w').close()
        try:
            mount(f'/dev/{nama}', target, None, MS_BIND)
        except OSError:
            pass
    if lapisan:
        # Level 04: overlay — rootfs dasar hanya dibaca; semua
        # tulisan mendarat di lapisan atas milik container ini.
        atas = os.path.join(lapisan, 'atas')
        kerja = os.path.join(lapisan, 'kerja')
        gabungan = os.path.join(lapisan, 'gabungan')
        for d in (atas, kerja, gabungan):
            os.makedirs(d, exist_ok=True)
        mount('overlay', gabungan, 'overlay', 0,
              f'lowerdir={rootfs},upperdir={atas},workdir={kerja}')
        rootfs = gabungan
    # pivot_root menuntut rootfs menjadi titik mount: bind ke diri sendiri.
    mount(rootfs, rootfs, None, MS_BIND | MS_REC)
    lama = os.path.join(rootfs, '.akar-lama')
    os.makedirs(lama, exist_ok=True)
    pivot_root(rootfs, lama)
    os.chdir('/')
    umount2('/.akar-lama', MNT_DETACH)
    os.rmdir('/.akar-lama')
    try:
        mount('proc', '/proc', 'proc', MS_NOSUID | MS_NODEV | MS_NOEXEC)
    except PermissionError:
        # Sandbox kami tinggal di dalam container lain yang /proc-nya
        # TERKUNCI (path bertopeng): kernel menolak mount proc baru
        # di userns turunannya — tembok yang sama yang menahan
        # rootless Docker di dalam container terbatas. Container
        # tetap berjalan; isolasi PID dibuktikan lewat NSpid host
        # (lihat uji_irisan2). Di host biasa mount ini berhasil.
        pass
    terapkan_batas(batas_memori_mb, batas_cpu_detik)
    os.execvp(argv[0], argv)


def run(rootfs, argv, hostname='wadah', lapisan=None,
        batas_memori_mb=None, batas_cpu_detik=None):
    """Fork dua tahap: anak masuk user+mount+UTS+PID+NET namespace
    (PID namespace hanya berlaku bagi anak-anaknya, jadi cucu yang
    menjadi PID 1 dan menjalankan perintah). Kode keluar diteruskan
    melewati kedua tahap."""
    pid = os.fork()
    if pid == 0:
        try:
            masuk_user_namespace()
            unshare(CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWPID | CLONE_NEWNET)
            cucu = os.fork()
            if cucu == 0:
                try:
                    _proses_utama(rootfs, argv, hostname, lapisan,
                                  batas_memori_mb, batas_cpu_detik)
                except BaseException:
                    os._exit(127)
            _, status = os.waitpid(cucu, 0)
            os._exit(_keluar_dari(status))
        except BaseException:
            os._exit(127)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == '__main__':
    args = sys.argv[1:]
    hostname = 'wadah'
    lapisan = None
    batas_memori = None
    batas_cpu = None
    while args and args[0].startswith('--'):
        opsi, nilai = args[0], args[1]
        args = args[2:]
        if opsi == '--hostname':
            hostname = nilai
        elif opsi == '--lapisan':
            lapisan = os.path.abspath(nilai)
        elif opsi == '--memori':
            batas_memori = int(nilai)
        elif opsi == '--cpu':
            batas_cpu = int(nilai)
        else:
            print(f'Opsi tak dikenal: {opsi}')
            raise SystemExit(2)
    if len(args) < 3 or args[0] != 'run':
        print('Pakai: python3 wadah.py [--hostname NAMA] [--lapisan DIR] '
              '[--memori MB] [--cpu DETIK] run <rootfs> <perintah> [arg...]')
        raise SystemExit(2)
    raise SystemExit(run(os.path.abspath(args[1]), args[2:], hostname,
                         lapisan, batas_memori, batas_cpu))
