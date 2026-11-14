"""Live spectrum of what the PC is playing, for the music bars.

A worker thread reads the default output device through WASAPI loopback (what the
speakers get, not the microphone), keeps the last fraction of a second in memory,
and turns it into a few bar heights. Audio is never stored, saved or sent.
The math is pure Python and has no window, so it is tested on its own.
"""
import cmath
import ctypes
from ctypes import POINTER, byref, c_void_p, c_uint32, c_uint64, c_int64, c_ulong, c_ushort, wintypes
import math
import struct
import time

from PyQt6.QtCore import QThread, pyqtSignal

N = 512                  # samples per analysis: about 11 ms at 48 kHz
LOW_HZ, HIGH_HZ = 60., 12000.
FLOOR_DB, CEIL_DB = -62., -14.
_WINDOW = [.5 - .5 * math.cos(2 * math.pi * i / (N - 1)) for i in range(N)]
_TWIDDLE = [cmath.exp(-2j * math.pi * k / N) for k in range(N // 2)]
_REVERSED = [int(format(i, '09b')[::-1], 2) for i in range(N)]


def fft(samples):
    """Radix-2 FFT of exactly N real samples; returns N complex bins."""
    a = [complex(samples[j] * _WINDOW[j]) for j in _REVERSED]
    size = 2
    while size <= N:
        half, step = size // 2, N // size
        for start in range(0, N, size):
            for k in range(half):
                odd = a[start + k + half] * _TWIDDLE[k * step]
                even = a[start + k]
                a[start + k], a[start + k + half] = even + odd, even - odd
        size *= 2
    return a


def band_edges(count, rate):
    """FFT bin ranges for `count` bars, spaced the way pitch is heard (logarithmically)."""
    edges = []
    for i in range(count + 1):
        hz = LOW_HZ * (HIGH_HZ / LOW_HZ) ** (i / count)
        edges.append(min(N // 2, max(1, round(hz * N / rate))))
    return [(edges[i], max(edges[i] + 1, edges[i + 1])) for i in range(count)]


def levels(samples, count, rate=48000):
    """`count` bar heights from 0 to 1 for N mono samples. Silence is all zeros."""
    if len(samples) < N:
        return [0.] * count
    bins = fft(samples[-N:])
    out = []
    for low, high in band_edges(count, rate):
        power = sum(abs(bins[i]) ** 2 for i in range(low, min(high, N // 2))) / max(1, high - low)
        db = 10 * math.log10(power / (N * N / 16) + 1e-12)
        out.append(max(0., min(1., (db - FLOOR_DB) / (CEIL_DB - FLOOR_DB))))
    return out


def smooth(previous, target, rise=.6, fall=.18):
    """Bars jump up with the beat and sink back slowly, like a real meter."""
    return [p + (t - p) * (rise if t > p else fall) for p, t in zip(previous, target)]


# -- WASAPI loopback ----------------------------------------------------------
class GUID(ctypes.Structure):
    _fields_ = [('a', c_ulong), ('b', c_ushort), ('c', c_ushort), ('d', ctypes.c_ubyte * 8)]

    def __init__(self, text):
        super().__init__()
        ctypes.oledll.ole32.CLSIDFromString(text, byref(self))


class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('tag', c_ushort), ('channels', c_ushort), ('rate', c_ulong), ('bytes_per_second', c_ulong),
                ('block', c_ushort), ('bits', c_ushort), ('extra', c_ushort),
                ('valid_bits', c_ushort), ('mask', c_ulong), ('sub', GUID)]


def _call(pointer, index, *args, types=()):
    """Call method `index` of a COM interface pointer; raises OSError on failure."""
    table = ctypes.cast(ctypes.cast(pointer, POINTER(c_void_p))[0], POINTER(c_void_p))
    method = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *types)(table[index])
    return method(pointer, *args)


def _release(pointer):
    if pointer:
        table = ctypes.cast(ctypes.cast(pointer, POINTER(c_void_p))[0], POINTER(c_void_p))
        ctypes.WINFUNCTYPE(c_ulong, c_void_p)(table[2])(pointer)


class SpectrumMonitor(QThread):
    """Emits bar heights about 30 times a second while it runs. start()/stop() as needed."""
    levels_ready = pyqtSignal(list)

    def __init__(self, bars=24, parent=None):
        super().__init__(parent)
        self.bars = bars
        self._running = False
        self.error = ''

    def stop(self):
        self._running = False
        return self.wait(1500)

    def run(self):
        self._running = True
        ole = ctypes.oledll.ole32
        ole.CoInitializeEx(None, 0)
        enumerator = device = client = capture = c_void_p()
        enumerator, device, client, capture, fmt = c_void_p(), c_void_p(), c_void_p(), c_void_p(), POINTER(WAVEFORMATEX)()
        try:
            ole.CoCreateInstance(byref(GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')), None, 1,
                                 byref(GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')), byref(enumerator))
            _call(enumerator, 4, 0, 0, byref(device), types=(c_uint32, c_uint32, POINTER(c_void_p)))
            _call(device, 3, byref(GUID('{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}')), 1, None, byref(client),
                  types=(POINTER(GUID), c_uint32, c_void_p, POINTER(c_void_p)))
            _call(client, 8, byref(fmt), types=(POINTER(POINTER(WAVEFORMATEX)),))
            w = fmt.contents
            is_float = w.bits == 32 and (w.tag == 3 or (w.tag == 0xFFFE and w.sub.a == 3))
            if not is_float or not 1 <= w.channels <= 8:
                raise OSError('unsupported mix format')
            _call(client, 3, 0, 0x00020000, 2000000, 0, fmt, None,
                  types=(c_uint32, c_uint32, c_int64, c_int64, POINTER(WAVEFORMATEX), c_void_p))
            _call(client, 14, byref(GUID('{C8ADBD64-E71E-48A0-A4DE-185C395CD317}')), byref(capture),
                  types=(POINTER(GUID), POINTER(c_void_p)))
            _call(client, 10)
            self._pump(capture, w.channels, w.rate)
            _call(client, 11)
        except OSError as error:
            self.error = str(error)   # no device, exclusive mode, RDP: the bars keep their idle look
        finally:
            if fmt:
                ole.CoTaskMemFree(fmt)
            for pointer in (capture, client, device, enumerator):
                _release(pointer)
            ole.CoUninitialize()
            self.levels_ready.emit([])

    def _pump(self, capture, channels, rate):
        mono, shown, last_emit, last_sound = [0.] * N, [0.] * self.bars, 0., time.monotonic()
        data, frames, flags = POINTER(ctypes.c_ubyte)(), c_uint32(), wintypes.DWORD()
        get = (POINTER(POINTER(ctypes.c_ubyte)), POINTER(c_uint32), POINTER(wintypes.DWORD), POINTER(c_uint64), POINTER(c_uint64))
        while self._running:
            packet = c_uint32()
            _call(capture, 5, byref(packet), types=(POINTER(c_uint32),))
            while packet.value:
                _call(capture, 3, byref(data), byref(frames), byref(flags), None, None, types=get)
                count = frames.value
                if count and not flags.value & 2:   # 2 = the buffer is silence
                    raw = ctypes.string_at(data, count * channels * 4)
                    values = struct.unpack('<%df' % (count * channels), raw)
                    mono.extend(sum(values[i:i + channels]) / channels for i in range(0, len(values), channels))
                    del mono[:-N]
                    last_sound = time.monotonic()
                _call(capture, 4, count, types=(c_uint32,))
                _call(capture, 5, byref(packet), types=(POINTER(c_uint32),))
            now = time.monotonic()
            if now - last_emit >= 1 / 30:
                last_emit = now
                target = levels(mono, self.bars, rate) if now - last_sound < .25 else [0.] * self.bars
                shown = smooth(shown, target)
                self.levels_ready.emit(shown)
            time.sleep(.008)
