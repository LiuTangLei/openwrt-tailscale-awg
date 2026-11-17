#!/usr/bin/env python3
"""Destructive fixture tests: run ONLY inside the dedicated private container.

Uses the real static ASUS binary, a 40 MiB flash fixture and private netfilter.
No host networking, production peers, credentials or router state are needed.
"""
import fcntl
import gzip
import hashlib
import json
import os
import pty
from pathlib import Path
import shutil
import signal
import select
import subprocess
import tempfile
import time
import unittest

REPO = Path('/repo')
MANAGER = REPO / 'asus/tailscale-asus'
HOME = Path('/jffs/addons/tailscale-awg')
RUN = Path('/tmp/tailscale-awg')
INPUTS = Path('/tmp/inputs')
ENV = dict(os.environ, TS_ASUS_HOME=str(HOME), TS_ASUS_RUN=str(RUN))
SHELL = os.environ.get('TEST_SHELL', '/bin/sh')
CORE = 'a32d18362c987e5007eab9f76c69118947a7b047'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(*args, expected=0, timeout=45):
    result = subprocess.run([SHELL, str(MANAGER), *args], env=ENV,
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode != expected:
        raise AssertionError(f'{args}: rc={result.returncode}, expected={expected}\n{result.stdout}\n{result.stderr}')
    return result.stdout + result.stderr


def make_bundle(release='v1.104.7', binary=None, **changes):
    INPUTS.mkdir(exist_ok=True)
    archive = INPUTS / f'{release}.gz'
    if binary is None:
        source = REPO / 'asus/out/tailscale-asus-v1.104.7-arm64.gz'
        shutil.copyfile(source, archive)
        raw = gzip.decompress(source.read_bytes())
    else:
        raw = binary
        archive.write_bytes(gzip.compress(binary, mtime=0))
    data = dict(format='1', release=release, version='1.104.7', arch='arm64',
                core=CORE, core_tag='v1.104.7', quic='v0.65.0-quic.4',
                go='go1.27.4', build_tags='ts_include_cli,ts_omit_clientupdate,ts_omit_flashappliance',
                sha256=sha(archive), binary_sha256=hashlib.sha256(raw).hexdigest(),
                binary_bytes=str(len(raw)), manager_sha256=sha(MANAGER))
    data.update(changes)
    manifest = archive.with_suffix('.manifest')
    manifest.write_text(''.join(f'{key}={value}\n' for key, value in data.items()))
    return archive, manifest


def install(bundle=None, platform='stock', expected=0):
    archive, manifest = bundle or make_bundle()
    return command('install', '--bundle', str(archive), '--manifest', str(manifest),
                   '--platform', platform, expected=expected)


def current():
    return (HOME / 'current').read_text().strip()


def wait_ready():
    # Boot hooks are intentionally asynchronous. A PID precedes LocalAPI and
    # completion of the start transaction; wait for both instead of racing it.
    for _ in range(150):
        if (RUN / 'tailscaled.sock').exists():
            with (RUN / 'lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except BlockingIOError:
                    pass
        time.sleep(.1)
    raise AssertionError('asynchronous startup did not complete')


class ManagerTests(unittest.TestCase):
    def bootstrap(self, merlin=False, corrupt=False, expected=0, mode='', preinstalled=False, terminal=False):
        if preinstalled:
            install()
        archive, manifest = make_bundle()
        (INPUTS / 'mirror-mode').write_text(mode)
        if corrupt:
            with archive.open('ab') as output:
                output.write(b'corrupt')
        if merlin:
            Path('/rom/etc/rc3.d/S45custom-init').unlink()
            Path('/rom/etc/init.d/custom-init.sh').unlink()
            (INPUTS / 'scripts-enabled').write_text('0\n')
            Path('/usr/sbin/nvram').write_text('''#!/bin/sh
case "$1:$2" in
get:rc_support) echo am_addons;;
get:jffs2_scripts) cat /tmp/inputs/scripts-enabled;;
set:jffs2_scripts=*) printf '%s\\n' "${2#*=}" > /tmp/inputs/scripts-enabled;;
commit:) :;;
*) exit 1;;
esac
''')
        real_curl = shutil.which('curl')
        fake_curl = Path('/usr/sbin/curl')
        fake_curl.write_text('''#!/bin/sh
case "$*" in *--version*|*--unix-socket*) exec ''' + real_curl + ''' "$@";; esac
while [ "$#" -gt 0 ]; do
 case "$1" in
 -o) output=$2; shift 2;;
 https://*) url=$1; shift;;
 *) shift;;
 esac
done
printf '%s\\n' "$url" >> /tmp/inputs/downloads.log
mode=$(cat /tmp/inputs/mirror-mode)
case "$mode:$url" in
html-first:https://gh-proxy.org/*) echo '<html>mirror unavailable</html>' > "$output"; exit 0;;
partial-first:https://gh-proxy.org/*) echo partial > "$output"; exit 28;;
failed:*) exit 28;;
no-payload:*.gz) exit 99;;
esac
case "$url" in
*/install-asus.sh) cp /repo/asus/install.sh "$output";;
*/tailscale-asus) cp /repo/asus/tailscale-asus "$output";;
*.gz.manifest) cp ''' + str(manifest) + ''' "$output";;
*.gz) cp ''' + str(archive) + ''' "$output";;
*) exit 1;;
esac
''')
        fake_curl.chmod(0o755)
        try:
            if terminal:
                pid, fd = pty.fork()
                if pid == 0:
                    os.execve(SHELL, [SHELL, str(REPO / 'asus/install.sh')], ENV)
                output = b''
                try:
                    os.write(fd, b'1\n6\n0\n')
                    deadline = time.monotonic() + 60
                    while time.monotonic() < deadline:
                        ready, _, _ = select.select([fd], [], [], 1)
                        if ready:
                            try:
                                chunk = os.read(fd, 65536)
                            except OSError:
                                break
                            if not chunk: break
                            output += chunk
                    else:
                        os.kill(pid, signal.SIGKILL)
                        self.fail('interactive menu did not exit')
                    _, status = os.waitpid(pid, 0)
                    self.assertTrue(os.WIFEXITED(status) and os.WEXITSTATUS(status) == expected, output.decode(errors='replace'))
                    return output.decode(errors='replace')
                finally:
                    os.close(fd)
            result = subprocess.run([SHELL], input=(REPO / 'asus/install.sh').read_text(),
                                    env=ENV, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            return result.stdout + result.stderr
        finally:
            fake_curl.unlink()

    def setUp(self):
        # ASUS also ships a hardware register tool named /usr/sbin/sh.
        decoy = Path('/usr/sbin/sh')
        decoy.write_text('#!/bin/sh\necho "vendor memory utility, not a shell" >&2\nexit 0\n')
        decoy.chmod(0o755)
        # ASUS BusyBox 1.24 is compiled without fractional sleep support.
        sleep = Path('/usr/sbin/sleep')
        sleep.write_text('#!/bin/sh\ncase "$1" in ""|*[!0-9]*) echo "integer sleep required" >&2; exit 1;; esac\nexec /bin/busybox sleep "$@"\n')
        sleep.chmod(0o755)
        # The stock image also omits the id applet; use /proc for EUID.
        no_id = Path('/usr/sbin/id')
        no_id.write_text('#!/bin/sh\necho "id applet unavailable" >&2\nexit 127\n')
        no_id.chmod(0o755)
        if (RUN / 'daemon.pid').exists():
            command('stop')
        for path in (HOME, RUN, INPUTS, Path('/jffs/scripts'), Path('/opt/etc/init.d')):
            if path.exists():
                shutil.rmtree(path)
        Path('/rom/etc/init.d').mkdir(parents=True, exist_ok=True)
        dispatcher = Path('/rom/etc/init.d/custom-init.sh')
        dispatcher.write_text('#!/bin/sh\nexit 0\n'); dispatcher.chmod(0o755)
        boot = Path('/rom/etc/rc3.d'); boot.mkdir(exist_ok=True)
        (boot / 'S45custom-init').unlink(missing_ok=True)
        (boot / 'S45custom-init').symlink_to('../init.d/custom-init.sh')
        Path('/jffs/scripts').mkdir(parents=True)
        nvram = Path('/usr/sbin/nvram')
        nvram.write_text('#!/bin/sh\ncase "$2" in jffs2_scripts) echo 1;; rc_support) echo am_addons;; esac\n')
        nvram.chmod(0o755)

    def tearDown(self):
        if (HOME / 'current').exists():
            command('stop')
        Path('/jffs/space-reservation').unlink(missing_ok=True)

    def test_01_real_daemon_ram_execution_and_offline_boot(self):
        install()
        self.assertIn('running', command('status'))
        self.assertIn('1.104.7', command('cli', 'version'))
        state = HOME / 'state/sentinel'; state.write_text('identity-must-survive')
        pid = (RUN / 'daemon.pid').read_text().split()[0]
        self.assertTrue(os.readlink(f'/proc/{pid}/exe').startswith(str(RUN)))
        self.assertFalse(list(HOME.rglob('tailscaled')))
        hooks = Path('/jffs/scripts/custom-init/tailscale-awg')
        command('stop')
        shutil.rmtree(RUN)  # boot has no unpacked binary and no network
        start = time.monotonic()
        subprocess.run([SHELL, str(hooks), 'start'], check=True)
        self.assertLess(time.monotonic() - start, 0.5)
        wait_ready()
        self.assertIn('running', command('status'))
        self.assertEqual(state.read_text(), 'identity-must-survive')
        command('restart')  # also verifies flock was not inherited by daemon

    def test_02_update_rollback_identity_and_two_slots(self):
        install()
        marker = HOME / 'state/test-identity'; marker.write_bytes(os.urandom(64)); original = sha(marker)
        install(make_bundle('v1.104.8'))
        self.assertEqual(current(), 'v1.104.8-arm64')
        command('rollback')
        self.assertEqual(current(), 'v1.104.7-arm64')
        self.assertEqual(sha(marker), original)
        install(make_bundle('v1.104.9'))
        slots = [p.name for p in (HOME / 'releases').iterdir()]
        self.assertCountEqual(slots, ['v1.104.7-arm64', 'v1.104.9-arm64'])
        self.assertEqual(sha(marker), original)

    def test_03_corrupt_payload_and_manifest_refused_before_stop(self):
        install(); old_pid = (RUN / 'daemon.pid').read_text()
        for changes in ({'arch': 'armv7'}, {'core': '0' * 40}, {'manager_sha256': '1' * 64}, {'binary_sha256': '2' * 64}):
            with self.subTest(changes=changes):
                install(make_bundle('v1.104.8', **changes), expected=1)
                self.assertEqual((RUN / 'daemon.pid').read_text(), old_pid)
                self.assertEqual(current(), 'v1.104.7-arm64')
        archive, manifest = make_bundle('v1.104.8')
        with archive.open('ab') as f: f.write(b'corruption')
        install((archive, manifest), expected=1)
        with manifest.open('a') as f: f.write('format=1\n')
        install((archive, manifest), expected=1)
        self.assertEqual((RUN / 'daemon.pid').read_text(), old_pid)

    def test_04_flash_full_keeps_active_archive_and_process(self):
        install(); old_pid = (RUN / 'daemon.pid').read_text()
        archive = HOME / 'releases' / current() / 'payload.gz'; original = sha(archive)
        free = shutil.disk_usage(HOME).free
        with Path('/jffs/space-reservation').open('wb') as f:
            chunk = b'x' * (1024 * 1024)
            for _ in range(max(0, free // len(chunk) - 12)): f.write(chunk)
        message = install(make_bundle('v1.104.8'), expected=1)
        self.assertIn('insufficient flash', message)
        self.assertEqual(sha(archive), original)
        self.assertEqual((RUN / 'daemon.pid').read_text(), old_pid)

    def test_05_failed_start_rolls_back(self):
        install(); identity = HOME / 'state/test-identity'; identity.write_text('keep')
        bad = f'#!/bin/sh\nif [ "${{1:-}}" = --version ]; then echo "{CORE}"; exit 0; fi\nexit 42\n'.encode()
        message = install(make_bundle('v1.104.8', binary=bad), expected=1)
        self.assertIn('startup failed', message)
        self.assertEqual(current(), 'v1.104.7-arm64')
        self.assertIn('running', command('status'))
        self.assertEqual(identity.read_text(), 'keep')

    def test_06_merlin_exit_no_newline_and_symlink_restore(self):
        script = Path('/jffs/scripts/services-start')
        original = b'#!/bin/sh\nprintf "user-hook:%s" "$1" > /tmp/original-ran\nexit 7'
        script.write_bytes(original); script.chmod(0o750)
        target = Path('/jffs/scripts/user-stop'); target.write_text('#!/bin/sh\nexit 0\n'); target.chmod(0o700)
        Path('/jffs/scripts/services-stop').symlink_to('user-stop')
        bash_hook = Path('/jffs/scripts/firewall-start')
        bash_original = '#!/bin/bash\nwords=(original bash)\nprintf "%s" "${words[1]}" > /tmp/bash-hook-ran\n'
        bash_hook.write_text(bash_original); bash_hook.chmod(0o755)
        install(platform='merlin')
        command('stop')
        result = subprocess.run([SHELL, str(script), 'argument'], capture_output=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(Path('/tmp/original-ran').read_text(), 'user-hook:argument')
        wait_ready()
        old_pid = (RUN / 'daemon.pid').read_text().split()[0]
        subprocess.run([SHELL, str(bash_hook)], check=True)
        self.assertEqual(Path('/tmp/bash-hook-ran').read_text(), 'bash')
        for _ in range(150):
            time.sleep(.1)
            if (RUN / 'daemon.pid').exists() and (RUN / 'daemon.pid').read_text().split()[0] != old_pid:
                break
        wait_ready()
        command('uninstall')
        self.assertEqual(script.read_bytes(), original)
        self.assertEqual(script.stat().st_mode & 0o777, 0o750)
        self.assertEqual(os.readlink('/jffs/scripts/services-stop'), 'user-stop')
        self.assertEqual(target.read_text(), '#!/bin/sh\nexit 0\n')
        self.assertEqual(bash_hook.read_text(), bash_original)

    def test_07_hook_collision_and_user_edits_preserved(self):
        hook = Path('/jffs/scripts/custom-init/tailscale-awg'); hook.parent.mkdir()
        hook.write_text('user-owned')
        install(expected=1)
        self.assertEqual(hook.read_text(), 'user-owned')
        hook.unlink(); install()
        hook.write_text(hook.read_text() + '# user edit\n')
        content = hook.read_bytes()
        command('uninstall', expected=1)
        self.assertEqual(hook.read_bytes(), content)
        self.assertIn('running', command('status'))

    def test_08_lock_foreign_pid_and_unsafe_runtime(self):
        install()
        with (RUN / 'lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertIn('another lifecycle', command('restart', expected=1))
        command('stop')
        sleeper = subprocess.Popen(['sleep', '60'])
        try:
            ticks = Path(f'/proc/{sleeper.pid}/stat').read_text().split()[21]
            (RUN / 'daemon.pid').write_text(f'{sleeper.pid} {ticks}\n')
            command('stop')
            self.assertIsNone(sleeper.poll())
        finally:
            sleeper.terminate(); sleeper.wait()
        result = subprocess.run([SHELL, str(MANAGER), 'start'], env=dict(ENV, TS_ASUS_RUN='/jffs/bad'), capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_09_entware_hook_without_package_conflicts(self):
        root = Path('/opt/etc/init.d'); root.mkdir(parents=True)
        (root / 'rc.unslung').write_text('#!/bin/sh\nexit 0\n'); (root / 'rc.unslung').chmod(0o755)
        install(platform='entware')
        self.assertTrue((root / 'S98tailscale-awg').is_file())
        command('uninstall')
        self.assertTrue((root / 'rc.unslung').is_file())
        self.assertFalse((root / 'S98tailscale-awg').exists())
        self.assertTrue((HOME / 'state').is_dir())

    def stalled_update(self):
        archive, manifest = make_bundle('v1.104.8', binary=(REPO / 'asus/out/stalled-daemon').read_bytes())
        output = (INPUTS / 'update.log').open('w')
        process = subprocess.Popen([SHELL, str(MANAGER), 'install', '--bundle', str(archive),
                                    '--manifest', str(manifest), '--platform', 'stock'], env=ENV,
                                   stdout=output, stderr=subprocess.STDOUT)
        output.close()
        for _ in range(250):
            if process.poll() is not None:
                self.fail((INPUTS / 'update.log').read_text())
            if (HOME / 'pending').exists() and current() == 'v1.104.8-arm64' and (RUN / 'daemon.pid').exists():
                pid = (RUN / 'daemon.pid').read_text().split()[0]
                if '/v1.104.8-arm64/tailscaled' in os.readlink(f'/proc/{pid}/exe'):
                    return process
            time.sleep(.05)
        process.terminate(); process.wait()
        self.fail('did not reach candidate readiness window')

    def test_10_cancel_activation_restores_previous(self):
        install(); marker = HOME / 'state/test-identity'; marker.write_text('keep')
        process = self.stalled_update()
        time.sleep(.5)
        self.assertLessEqual((RUN / 'daemon.log').stat().st_size, 262144)
        process.terminate(); process.wait(timeout=30)
        self.assertEqual(process.returncode, 143)
        self.assertEqual(current(), 'v1.104.7-arm64')
        self.assertIn('running', command('status'))
        self.assertFalse((HOME / 'pending').exists())
        self.assertEqual(marker.read_text(), 'keep')

    def test_11_killed_installer_recovers_from_durable_pending(self):
        install(); marker = HOME / 'state/test-identity'; marker.write_text('keep')
        process = self.stalled_update()
        process.kill(); process.wait(timeout=5)  # SIGKILL cannot run an EXIT trap
        self.assertTrue((HOME / 'pending').exists())
        # A real power cut also kills the daemon/supervisor, rather than
        # allowing their in-memory readiness transaction to keep running.
        for name in ('worker', 'daemon'):
            pid = int((RUN / f'{name}.pid').read_text().split()[0])
            os.kill(pid, signal.SIGKILL)
        shutil.rmtree(RUN)  # loss of all RAM artifacts, as on a power cut
        message = command('start')
        self.assertIn('recovered interrupted update', message)
        self.assertEqual(current(), 'v1.104.7-arm64')
        self.assertIn('running', command('status'))
        self.assertEqual(marker.read_text(), 'keep')

    def test_12_daemon_crash_supervision(self):
        install()
        old_pid = int((RUN / 'daemon.pid').read_text().split()[0])
        os.kill(old_pid, signal.SIGKILL)
        for _ in range(150):
            time.sleep(.1)
            if (RUN / 'daemon.pid').exists():
                new_pid = int((RUN / 'daemon.pid').read_text().split()[0])
                if new_pid != old_pid and (RUN / 'tailscaled.sock').exists():
                    break
        self.assertNotEqual(new_pid, old_pid)
        wait_ready()
        self.assertIn('running', command('status'))

    def test_13_logged_in_private_control_and_firewall_recovery(self):
        # This control/DERP fixture is entirely loopback in the container.
        # It is not the user's WAN DERP path and supplies no production keys.
        # --network=none leaves only loopback, so Tailscale correctly pauses
        # its control client. Supply a private dummy link, without a gateway.
        subprocess.run(['ip', 'link', 'add', 'asus-test0', 'type', 'dummy'], check=True)
        subprocess.run(['ip', 'addr', 'add', '192.0.2.1/24', 'dev', 'asus-test0'], check=True)
        subprocess.run(['ip', 'link', 'set', 'asus-test0', 'up'], check=True)
        with (INPUTS.parent / 'control.log').open('w') as output:
            control = subprocess.Popen([str(REPO / 'asus/out/testcontrol'), '--addr=127.0.0.1:9911'], stdout=output, stderr=subprocess.STDOUT)
        try:
            install()
            command('cli', 'up', '--login-server=http://127.0.0.1:9911', '--accept-dns=false', '--accept-routes=false', '--timeout=15s')
            status = json.loads(command('cli', 'status', '--json'))
            self.assertEqual(status['BackendState'], 'Running')
            old_pid = (RUN / 'daemon.pid').read_text().split()[0]
            time.sleep(4)  # supervisor has observed the established jump
            subprocess.run(['iptables', '-C', 'INPUT', '-j', 'ts-input'], check=True)
            subprocess.run(['iptables', '-D', 'INPUT', '-j', 'ts-input'], check=True)
            for _ in range(150):
                time.sleep(.1)
                if (RUN / 'daemon.pid').exists() and (RUN / 'daemon.pid').read_text().split()[0] != old_pid:
                    break
            wait_ready()
            subprocess.run(['iptables', '-C', 'INPUT', '-j', 'ts-input'], check=True)
            self.assertEqual(json.loads(command('cli', 'status', '--json'))['Self']['PublicKey'], status['Self']['PublicKey'])
        finally:
            control.terminate(); control.wait(timeout=5)
            subprocess.run(['ip', 'link', 'del', 'asus-test0'], check=True)

    @unittest.skipUnless(os.environ.get('TS_ASUS_BASELINE_BUNDLE'), 'set TS_ASUS_BASELINE_BUNDLE for actual 1.104.6 cross-core rollback')
    def test_14_cross_core_update_and_rollback(self):
        old_core = '42e1cdcb7e058f64104aa7f4f42e7b3dda015253'
        old_raw = gzip.decompress(Path(os.environ['TS_ASUS_BASELINE_BUNDLE']).read_bytes())
        old_manager = INPUTS / 'old-manager'; INPUTS.mkdir(exist_ok=True)
        old_manager.write_text(MANAGER.read_text().replace(CORE, old_core).replace('1.104.7', '1.104.6'))
        archive, manifest = make_bundle('v1.104.6', binary=old_raw, core=old_core,
                                        core_tag='v1.104.6', version='1.104.6', manager_sha256=sha(old_manager))
        result = subprocess.run([SHELL, str(old_manager), 'install', '--bundle', str(archive),
                                 '--manifest', str(manifest), '--platform', 'stock'], env=ENV, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertIn('1.104.6', command('cli', 'version'))
        install(make_bundle('v1.104.8', binary=(REPO / 'asus/out/stalled-daemon').read_bytes()), expected=1)
        self.assertEqual(current(), 'v1.104.6-arm64')
        self.assertIn('1.104.6', command('cli', 'version'))
        install()
        self.assertIn('1.104.7', command('cli', 'version'))
        command('rollback')
        self.assertEqual(current(), 'v1.104.6-arm64')
        self.assertIn('1.104.6', command('cli', 'version'))

    def test_15_missing_socket_restarts_owned_daemon(self):
        install()
        old_pid = int((RUN / 'daemon.pid').read_text().split()[0])
        (RUN / 'tailscaled.sock').unlink()
        try:
            command('start')
            try:
                still_owned = os.readlink(f'/proc/{old_pid}/exe').startswith(str(RUN))
            except FileNotFoundError:
                still_owned = False
            self.assertFalse(still_owned, 'old daemon must stop before recreating the socket')
        finally:
            try:
                if os.readlink(f'/proc/{old_pid}/exe').startswith(str(RUN)):
                    os.kill(old_pid, signal.SIGTERM)
            except FileNotFoundError:
                pass

    def test_16_orphan_slot_after_interrupted_flash_copy(self):
        install()
        marker = HOME / 'state/test-identity'; marker.write_text('keep')
        orphan = HOME / 'releases/v1.104.9-arm64'
        shutil.copytree(HOME / 'releases' / current(), orphan)
        install(make_bundle('v1.104.8'))
        self.assertFalse(orphan.exists())
        self.assertEqual(current(), 'v1.104.8-arm64')
        self.assertEqual(marker.read_text(), 'keep')

    def test_17_merlin_without_sha256sum(self):
        hidden = []
        try:
            for folder in ['/usr/sbin', '/usr/bin', '/sbin', '/bin', '/opt/sbin', '/opt/bin']:
                path = Path(folder) / 'sha256sum'
                if os.path.lexists(path):
                    backup = path.with_name('sha256sum.merlin-test-hidden')
                    path.rename(backup)
                    hidden.append((path, backup))
            self.assertIsNone(shutil.which('sha256sum'))
            subprocess.run(['openssl', 'version'], check=True, capture_output=True)
            install(platform='merlin')
            for line in (HOME / 'hooks.sha256').read_text().splitlines():
                digest, path = line.split('  ', 1)
                self.assertEqual(digest, sha(path))
            old_pid = (RUN / 'daemon.pid').read_text()
            archive, manifest = make_bundle('v1.104.8')
            with archive.open('ab') as output:
                output.write(b'corrupt')
            install((archive, manifest), platform='merlin', expected=1)
            self.assertEqual((RUN / 'daemon.pid').read_text(), old_pid)
            command('stop')
            subprocess.run([SHELL, '/jffs/scripts/services-start'], check=True)
            wait_ready()
            self.assertIn('running', command('status'))
            command('uninstall')
            self.assertFalse(Path('/jffs/scripts/services-start').exists())
        finally:
            if (HOME / 'current').exists():
                command('stop')
            for path, backup in reversed(hidden):
                backup.rename(path)

    def test_18_one_command_stock(self):
        self.bootstrap()
        self.assertEqual((HOME / 'platform').read_text().strip(), 'stock')
        self.assertIn('running', command('status'))

    def test_19_one_command_merlin_enables_scripts(self):
        self.bootstrap(merlin=True)
        self.assertEqual((INPUTS / 'scripts-enabled').read_text().strip(), '1')
        self.assertEqual((HOME / 'platform').read_text().strip(), 'merlin')
        self.assertIn('running', command('status'))

    def test_20_one_command_failure_restores_script_setting(self):
        self.bootstrap(merlin=True, corrupt=True, expected=1)
        self.assertEqual((INPUTS / 'scripts-enabled').read_text().strip(), '0')
        self.assertFalse((HOME / 'current').exists())

    def test_21_mirror_html_is_rejected_and_next_source_used(self):
        output = self.bootstrap(mode='html-first')
        self.assertIn('invalid or stale mirror metadata', output)
        self.assertIn('https://ghfast.top', output)
        self.assertIn('running', command('status'))

    def test_22_partial_download_falls_back(self):
        output = self.bootstrap(mode='partial-first')
        self.assertIn('https://ghfast.top', output)
        self.assertIn('running', command('status'))

    def test_23_repeated_install_keeps_pid_and_skips_payload(self):
        install()
        pid = (RUN / 'daemon.pid').read_text()
        output = self.bootstrap(mode='no-payload')
        self.assertIn('already installed', output)
        self.assertEqual(pid, (RUN / 'daemon.pid').read_text())
        urls = (INPUTS / 'downloads.log').read_text().splitlines()
        self.assertFalse(any(url.endswith('.gz') for url in urls))

    def test_24_failed_mirrors_preserve_running_service(self):
        install()
        pid = (RUN / 'daemon.pid').read_text()
        self.bootstrap(mode='failed', expected=1)
        self.assertEqual(pid, (RUN / 'daemon.pid').read_text())
        self.assertIn('running', command('status'))

    def test_25_menu_status_update_and_exit(self):
        output = self.bootstrap(mode='no-payload', preinstalled=True, terminal=True)
        self.assertIn('华硕 Tailscale AWG / QUIC', output)
        self.assertIn('already installed', output)
        self.assertEqual(output.count('华硕 Tailscale AWG / QUIC'), 3)
        self.assertIn('running', command('status'))

    def test_26_reopen_respects_disabled_merlin_boot_scripts(self):
        install(platform='merlin')
        pid = (RUN / 'daemon.pid').read_text()
        self.bootstrap(merlin=True, mode='no-payload')
        self.assertEqual((INPUTS / 'scripts-enabled').read_text().strip(), '0')
        self.assertEqual((RUN / 'daemon.pid').read_text(), pid)


if __name__ == '__main__':
    if not Path('/.dockerenv').exists() or os.environ.get('TS_ASUS_TEST_CONTAINER') != '1':
        raise SystemExit('Refusing to run outside the dedicated private test container')
    unittest.main(verbosity=2)
