"""What the modes measure: a post-match GPU report and a battery forecast against today's tasks."""
import datetime
import subprocess
import threading
import time

from mode_system import NO_WINDOW

SAMPLE_SECONDS = 5
GPU_FIELDS = ('temperature.gpu', 'utilization.gpu', 'clocks_event_reasons.hw_thermal_slowdown',
              'clocks_event_reasons.sw_thermal_slowdown', 'clocks_event_reasons.sw_power_cap')


def parse_sample(line):
    """One `nvidia-smi --format=csv,noheader,nounits` row, or None when it is not readable."""
    parts = [part.strip() for part in line.split(',')]
    if len(parts) != len(GPU_FIELDS):
        return None
    try:
        temperature, utilization = round(float(parts[0])), round(float(parts[1]))
    except ValueError:
        return None
    return {'temperature': temperature, 'utilization': utilization,
            'heat_limited': 'Active' in (parts[2], parts[3]),
            'power_limited': parts[4] == 'Active'}


class MatchStats:
    def __init__(self, started):
        self.started = started
        self.samples = 0
        self.peak = None
        self.utilization = 0
        self.heat = 0
        self.power = 0

    def add(self, sample):
        self.samples += 1
        self.peak = sample['temperature'] if self.peak is None else max(self.peak, sample['temperature'])
        self.utilization += sample['utilization']
        self.heat += sample['heat_limited']
        self.power += sample['power_limited']

    @staticmethod
    def _minutes(samples):
        minutes = round(samples * SAMPLE_SECONDS / 60)
        return f'{minutes} min' if minutes else 'under 1 min'

    def report(self, ended):
        minutes = max(0, round((ended - self.started) / 60))
        if not self.samples:
            return f'{minutes} min · no GPU readings'
        parts = [f'{minutes} min', f'peak {self.peak}°C', f'GPU {round(self.utilization / self.samples)}% busy',
                 f'slowed by heat {self._minutes(self.heat)}' if self.heat else 'no heat slowdown']
        if self.power:
            parts.append(f'power-capped {self._minutes(self.power)}')
        return ' · '.join(parts)


def query_gpu():
    """One short `nvidia-smi` query; a long-lived `-l` reader would outlive a crashed Daisy."""
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=' + ','.join(GPU_FIELDS),
                                 '--format=csv,noheader,nounits'], capture_output=True, text=True,
                                timeout=4, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_sample(result.stdout.strip().splitlines()[0]) if result.stdout.strip() else None


class GpuSampler:
    """Samples the GPU every few seconds from a daemon thread for the length of Gaming mode."""

    def __init__(self, clock=time.time, query=query_gpu, interval=SAMPLE_SECONDS):
        self.clock = clock
        self.query = query
        self.interval = interval
        self.stats = None
        self._stop = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        self.stats = MatchStats(self.clock())
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(self._stop,), name='daisy-gpu', daemon=True)
        self._thread.start()

    def _run(self, stop):
        while not stop.is_set():
            sample = self.query()
            with self._lock:
                if sample is not None and self.stats is not None:
                    self.stats.add(sample)
            stop.wait(self.interval)

    def stop(self):
        """End sampling; returns the report text, or '' if sampling never started."""
        if self.stats is None:
            return ''
        self._stop.set()
        self._thread.join(5)
        with self._lock:
            report, self.stats = self.stats.report(self.clock()), None
        return report


def parse_task_time(text, today):
    for pattern in ('%I:%M %p', '%H:%M'):
        try:
            clock = datetime.datetime.strptime(text.strip(), pattern).time()
            return datetime.datetime.combine(today, clock)
        except (ValueError, AttributeError):
            continue
    return None


class BatteryForecast:
    """Learn this laptop's real drain from percent readings while it is unplugged."""
    WINDOW = 45 * 60
    MIN_SPAN = 10 * 60
    FLOOR = 10

    def __init__(self):
        self.samples = []

    def add(self, now, percent, plugged):
        if plugged or percent is None:
            self.samples.clear()
            return
        self.samples.append((now, percent))
        self.samples = [(t, p) for t, p in self.samples if now - t <= self.WINDOW]

    def empty_at(self, now, percent, windows_secs=None):
        """(when the battery reaches 10%, 'measured' or 'Windows estimate'), or None."""
        if percent is None or percent <= self.FLOOR:
            return None
        if self.samples and now - self.samples[0][0] >= self.MIN_SPAN:
            start, first = self.samples[0]
            drop_per_second = (first - percent) / (now - start)
            if first - percent >= 2 and drop_per_second > 0:
                seconds = (percent - self.FLOOR) / drop_per_second
                return datetime.datetime.fromtimestamp(now + seconds), 'measured'
        if isinstance(windows_secs, (int, float)) and 0 < windows_secs < 24 * 3600:
            seconds = windows_secs * (percent - self.FLOOR) / percent
            return datetime.datetime.fromtimestamp(now + seconds), 'Windows estimate'
        return None

    @staticmethod
    def conflict(empty_at, tasks, now):
        """The first task today that starts after the battery would reach 10%."""
        upcoming = []
        for task in tasks:
            start = parse_task_time(task.get('time', ''), now.date())
            if start is not None and start > now:
                upcoming.append((start, task.get('name', 'your next task')))
        late = [item for item in sorted(upcoming) if item[0] > empty_at]
        return late[0] if late else None


def clock_text(moment):
    return moment.strftime('%I:%M %p').lstrip('0')
