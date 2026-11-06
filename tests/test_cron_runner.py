"""Exercise the rendered runner with fake executables; no cluster or cron writes."""
import os
import signal
import sys
import time
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNNER = yaml.safe_load((ROOT / 'gitops/base/app-values.yaml').read_text())['cronjob']['sidecar']['command'][-1]


class RunnerGate(unittest.TestCase):
    def run_runner(self, ready):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            scripts = {
                'php': '#!/bin/sh\nexit "$READY"\n',
                'timeout': '#!/bin/sh\nprintf "%s\\n" "$*" >> "$TRACE"\nexit 0\n',
                'sleep': '#!/bin/sh\nkill -TERM "$PPID"\n',
            }
            for name, content in scripts.items():
                executable = folder / name
                executable.write_text(content)
                executable.chmod(0o700)
            trace = folder / 'trace'
            env = dict(os.environ, PATH=str(folder), READY='0' if ready else '1', TRACE=str(trace))
            result = subprocess.run(['/bin/sh', '-c', RUNNER], env=env, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            return trace.read_text().splitlines() if trace.exists() else [], result.stderr

    def test_unready_web_never_runs_cron(self):
        runs, log = self.run_runner(False)
        self.assertEqual(runs, [])
        self.assertIn('waiting for initialized', log)

    def test_ready_web_runs_bounded_cron(self):
        runs, _ = self.run_runner(True)
        self.assertEqual(runs, ['--signal=TERM --kill-after=10s 900s php -d memory_limit=96M -f /var/www/html/cron.php'])

    def test_termination_reaches_active_cron_child(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            php = folder / 'php'
            php.write_text('#!/bin/sh\nexit 0\n')
            php.chmod(0o700)
            timeout = folder / 'timeout'
            timeout.write_text(f"#!{sys.executable}\n" +
                "import os, signal, time\n" +
                "from pathlib import Path\n" +
                "p=Path(os.environ['TRACE'])\n" +
                "def stop(*args):\n p.write_text('terminated')\n raise SystemExit(0)\n" +
                "signal.signal(signal.SIGTERM, stop)\n" +
                "p.write_text('started')\n" +
                "while True: time.sleep(0.01)\n")
            timeout.chmod(0o700)
            trace = folder / 'trace'
            process = subprocess.Popen(['/bin/sh', '-c', RUNNER],
                env=dict(os.environ, PATH=str(folder), TRACE=str(trace)),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                deadline = time.monotonic() + 3
                while not trace.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(trace.exists(), 'cron child did not start')
                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=3), 0)
                self.assertEqual(trace.read_text(), 'terminated')
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()

    def test_runner_shell_syntax(self):
        subprocess.run(['/bin/sh', '-n'], input=RUNNER, text=True, check=True)
