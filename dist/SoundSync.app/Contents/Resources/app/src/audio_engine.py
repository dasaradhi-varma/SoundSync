"""
SoundSync Multi-Out - Audio Engine
High-performance cross-platform multi-device audio capture and broadcast engine.
Supports Windows (WASAPI Loopback) and macOS (Core Audio with BlackHole / native aggregate).
Routes audio simultaneously to multiple output endpoints (AirPods, Bluetooth headphones, speakers)
with independent volume, mute, delay sync compensation, and real-time VU metering.
"""

import sys
import time
import math
import queue
import threading
import logging
import subprocess
from typing import Dict, List, Optional, Any
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AudioEngine")

IS_WINDOWS = (sys.platform == "win32")
IS_MAC = (sys.platform == "darwin")

# Resolve audio backend
pyaudio = None
BACKEND_NAME = "none"

if IS_WINDOWS:
    try:
        import pyaudiowpatch as pyaudio
        BACKEND_NAME = "pyaudiowpatch"
    except ImportError:
        try:
            import pyaudio
            BACKEND_NAME = "pyaudio"
        except ImportError:
            pass

if pyaudio is None:
    try:
        import pyaudio
        BACKEND_NAME = "pyaudio"
    except ImportError:
        pass


class SoundDeviceStream:
    """Wraps sounddevice RawStream to match PyAudio Stream interface."""
    def __init__(self, stream):
        self._stream = stream
        self._active = True
        try:
            self._stream.start()
        except Exception:
            pass

    def write(self, data: bytes):
        self._stream.write(data)

    def read(self, num_frames: int, exception_on_overflow: bool = False) -> bytes:
        data, overflowed = self._stream.read(num_frames)
        return bytes(data)

    def stop_stream(self):
        try:
            self._stream.stop()
        except Exception:
            pass
        self._active = False

    def close(self):
        try:
            self._stream.close()
        except Exception:
            pass
        self._active = False

    def is_active(self) -> bool:
        return self._active


class SoundDevicePyAudioCompat:
    """Provides a PyAudio-compatible interface using sounddevice on macOS & Linux."""
    paFloat32 = 1
    paWASAPI = 11
    paCoreAudio = 4

    def __init__(self):
        import sounddevice as sd
        self.sd = sd

    def get_device_count(self) -> int:
        try:
            return len(self.sd.query_devices())
        except Exception:
            return 0

    def get_device_info_by_index(self, index: int) -> dict:
        d = self.sd.query_devices(index)
        return {
            'index': index,
            'name': d['name'],
            'maxInputChannels': int(d['max_input_channels']),
            'maxOutputChannels': int(d['max_output_channels']),
            'defaultSampleRate': float(d['default_samplerate']),
            'hostApi': d['hostapi']
        }

    def get_host_api_info_by_type(self, host_api_type):
        return {'index': 0, 'name': 'Core Audio' if IS_MAC else 'Default'}

    def get_default_output_device_info(self) -> Optional[dict]:
        try:
            def_idx = self.sd.default.device[1]
            if def_idx is not None and def_idx >= 0:
                return self.get_device_info_by_index(def_idx)
        except Exception:
            pass
        return None

    def get_default_input_device_info(self) -> Optional[dict]:
        try:
            def_idx = self.sd.default.device[0]
            if def_idx is not None and def_idx >= 0:
                return self.get_device_info_by_index(def_idx)
        except Exception:
            pass
        return None

    def open(self, format=None, channels=2, rate=48000, input=False, output=False,
             input_device_index=None, output_device_index=None, frames_per_buffer=1024):
        if output:
            stream = self.sd.RawOutputStream(
                samplerate=rate,
                blocksize=frames_per_buffer,
                device=output_device_index,
                channels=channels,
                dtype='float32'
            )
            return SoundDeviceStream(stream)
        elif input:
            stream = self.sd.RawInputStream(
                samplerate=rate,
                blocksize=frames_per_buffer,
                device=input_device_index,
                channels=channels,
                dtype='float32'
            )
            return SoundDeviceStream(stream)
        else:
            raise ValueError("Must specify input=True or output=True")

    def terminate(self):
        pass


def create_audio_interface():
    """Returns an active PyAudio or SoundDevice compatibility instance."""
    global BACKEND_NAME
    if pyaudio is not None:
        try:
            inst = pyaudio.PyAudio()
            return inst
        except Exception as e:
            logger.warning(f"PyAudio initialization warning: {e}, using SoundDevice fallback.")
    BACKEND_NAME = "sounddevice"
    return SoundDevicePyAudioCompat()


def get_hardware_system_volume() -> tuple[float, bool]:
    """Reads system master volume and mute state on Windows or macOS."""
    if IS_WINDOWS:
        try:
            from pycaw.pycaw import AudioUtilities
            spk = AudioUtilities.GetSpeakers()
            return round(spk.volume_percent / 100.0, 2), bool(spk.EndpointVolume.GetMute())
        except Exception:
            pass
    elif IS_MAC:
        try:
            res_vol = subprocess.check_output(["osascript", "-e", "output volume of (get volume settings)"], stderr=subprocess.DEVNULL).decode().strip()
            res_mute = subprocess.check_output(["osascript", "-e", "output muted of (get volume settings)"], stderr=subprocess.DEVNULL).decode().strip()
            return round(int(res_vol) / 100.0, 2), (res_mute.lower() == "true")
        except Exception:
            pass
    return 1.0, False


def sync_hardware_system_volume(volume: Optional[float] = None, muted: Optional[bool] = None):
    """Sets system master volume and mute state on Windows or macOS."""
    if IS_WINDOWS:
        try:
            from pycaw.pycaw import AudioUtilities
            spk = AudioUtilities.GetSpeakers()
            if volume is not None:
                spk.volume_percent = max(0.0, min(float(volume), 1.0)) * 100.0
            if muted is not None:
                spk.EndpointVolume.SetMute(1 if muted else 0, None)
        except Exception as e:
            logger.debug(f"Windows volume sync note: {e}")
    elif IS_MAC:
        try:
            if volume is not None:
                pct = int(max(0.0, min(float(volume), 1.0)) * 100)
                subprocess.run(["osascript", "-e", f"set volume output volume {pct}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if muted is not None:
                mute_str = "true" if muted else "false"
                subprocess.run(["osascript", "-e", f"set volume output muted {mute_str}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"macOS volume sync note: {e}")



class FastDelayLine:
    """Ultra-low latency circular buffer for audio delay compensation."""
    def __init__(self, max_delay_ms: float = 1000.0, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_samples = int(sample_rate * (max_delay_ms / 1000.0))
        self.buffer = np.zeros((self.max_samples, channels), dtype=np.float32)
        self.write_pos = 0
        self.delay_samples = 0

    def set_delay_ms(self, delay_ms: float):
        delay_ms = max(0.0, min(float(delay_ms), 1000.0))
        self.delay_samples = int(self.sample_rate * (delay_ms / 1000.0))

    def process(self, chunk: np.ndarray) -> np.ndarray:
        if self.delay_samples == 0:
            return chunk
        n = len(chunk)
        if n > self.max_samples or n == 0:
            return chunk

        wp = self.write_pos
        # Circular write
        if wp + n <= self.max_samples:
            self.buffer[wp:wp + n] = chunk
        else:
            p1 = self.max_samples - wp
            self.buffer[wp:] = chunk[:p1]
            self.buffer[:n - p1] = chunk[p1:]

        # Circular read
        rp = (wp - self.delay_samples) % self.max_samples
        if rp + n <= self.max_samples:
            out = self.buffer[rp:rp + n].copy()
        else:
            p1 = self.max_samples - rp
            out = np.empty_like(chunk)
            out[:p1] = self.buffer[rp:]
            out[p1:] = self.buffer[:n - p1]

        self.write_pos = (wp + n) % self.max_samples
        return out


class OutputDeviceWorker(threading.Thread):
    """
    Dedicated streaming worker thread for a single audio output endpoint.
    Maintains independent queue, delay compensation line, volume gain, mute, and VU meter.
    """
    def __init__(
        self,
        p_inst: pyaudio.PyAudio,
        device_info: dict,
        target_sample_rate: int = 48000,
        channels: int = 2,
        frames_per_buffer: int = 1024,
        volume: float = 1.0,
        muted: bool = False,
        delay_ms: float = 0.0,
        pan: float = 0.0
    ):
        super().__init__(name=f"Worker-{device_info['name'][:20]}", daemon=True)
        self.p_inst = p_inst
        self.device_info = device_info
        self.device_index = device_info['index']
        self.device_name = device_info['name']
        self.sample_rate = int(device_info.get('sample_rate') or device_info.get('defaultSampleRate') or target_sample_rate)
        self.input_sample_rate = target_sample_rate
        
        dev_max_ch = device_info.get('channels') or device_info.get('maxOutputChannels') or 2
        self.channels = min(2, max(1, int(dev_max_ch)))
        self.frames_per_buffer = frames_per_buffer

        self.volume = volume
        self.muted = muted
        self.pan = pan
        self.delay_line = FastDelayLine(max_delay_ms=1000.0, sample_rate=target_sample_rate, channels=2)
        self.delay_line.set_delay_ms(delay_ms)

        self.audio_queue = queue.Queue(maxsize=80)
        self.running = False
        self.stream: Optional[pyaudio.Stream] = None
        self.current_level = 0.0
        self.error_message: Optional[str] = None

    def update_settings(self, volume: Optional[float] = None, muted: Optional[bool] = None, delay_ms: Optional[float] = None, pan: Optional[float] = None):
        if volume is not None:
            self.volume = max(0.0, min(float(volume), 2.0))
        if muted is not None:
            self.muted = bool(muted)
        if delay_ms is not None:
            self.delay_line.set_delay_ms(float(delay_ms))
        if pan is not None:
            self.pan = max(-1.0, min(float(pan), 1.0))

    def push_audio(self, chunk: np.ndarray):
        """Called by audio router to push incoming audio chunk to worker queue."""
        if not self.running:
            return
        try:
            self.audio_queue.put_nowait(chunk)
        except queue.Full:
            try:
                _ = self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(chunk)
            except (queue.Empty, queue.Full):
                pass

    def open_stream(self) -> bool:
        """Opens output audio stream synchronously before thread launch."""
        logger.info(f"Opening output stream for '{self.device_name}' (idx {self.device_index}, sr {self.sample_rate}, ch {self.channels})")
        try:
            self.stream = self.p_inst.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                output_device_index=self.device_index,
                frames_per_buffer=self.frames_per_buffer
            )
            return True
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"Failed to open audio stream for {self.device_name}: {e}")
            return False

    def close_stream(self):
        """Safely stops and closes output stream."""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        except Exception:
            pass
        self.stream = None
        logger.info(f"Output stream stopped for '{self.device_name}'")

    def run(self):
        if not self.stream:
            if not self.open_stream():
                self.running = False
                return

        self.running = True

        while self.running:
            try:
                raw_chunk = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                self.current_level = max(0.0, self.current_level * 0.8)
                continue

            if self.muted or self.volume <= 0.001:
                self.current_level = 0.0
                try:
                    silence = np.zeros((len(raw_chunk), self.channels), dtype=np.float32).tobytes()
                    if self.stream:
                        self.stream.write(silence)
                except Exception:
                    pass
                continue

            try:
                # 1. Apply Delay Line (operates on stereo)
                chunk = self.delay_line.process(raw_chunk)

                # 2. Resample if hardware requires different sample rate
                if self.sample_rate != self.input_sample_rate and len(chunk) > 1:
                    n_samples = len(chunk)
                    out_samples = int(np.round(n_samples * self.sample_rate / self.input_sample_rate))
                    orig_idx = np.linspace(0, n_samples - 1, num=n_samples)
                    tgt_idx = np.linspace(0, n_samples - 1, num=out_samples)
                    resampled = np.empty((out_samples, chunk.shape[1]), dtype=np.float32)
                    for ch in range(chunk.shape[1]):
                        resampled[:, ch] = np.interp(tgt_idx, orig_idx, chunk[:, ch])
                    chunk = resampled

                # 3. Channel format matching (mono/stereo)
                if self.channels == 1 and chunk.shape[1] > 1:
                    chunk = np.mean(chunk, axis=1, keepdims=True)
                elif self.channels == 2 and chunk.shape[1] == 1:
                    chunk = np.column_stack((chunk, chunk))

                # 4. Apply Volume & Pan
                if self.volume != 1.0 or self.pan != 0.0:
                    chunk = chunk * self.volume
                    if self.channels == 2:
                        if self.pan < 0.0:
                            chunk[:, 1] *= (1.0 + self.pan)
                        elif self.pan > 0.0:
                            chunk[:, 0] *= (1.0 - self.pan)

                # 5. Soft clipping protection
                np.clip(chunk, -1.0, 1.0, out=chunk)

                # 6. Measure VU Level (peak RMS)
                rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
                self.current_level = min(1.0, rms * 3.5)

                # 7. Stream to Windows Audio endpoint
                data_bytes = chunk.tobytes()
                if self.stream:
                    self.stream.write(data_bytes)
            except Exception as e:
                logger.warning(f"Write error on {self.device_name}: {e}")
                time.sleep(0.01)

        self.close_stream()

    def stop(self):
        self.running = False


class AudioRouter:
    """
    Master Audio Router and Loopback Manager.
    Manages WASAPI device enumeration, loopback capture stream, and active worker streams.
    """
    def __init__(self):
        self.p: Optional[pyaudio.PyAudio] = None
        self.wasapi_info: Optional[dict] = None
        self.all_devices: List[dict] = []
        self.default_output_device: Optional[dict] = None
        self.default_loopback_device: Optional[dict] = None

        self.is_broadcasting: bool = False
        self.capture_stream: Optional[pyaudio.Stream] = None
        self.capture_thread: Optional[threading.Thread] = None

        self.workers: Dict[int, OutputDeviceWorker] = {}
        self.device_configs: Dict[int, dict] = {} # user settings: volume, muted, delay_ms, enabled, pan

        self.master_volume: float = 1.0
        self.master_muted: bool = False
        self.mirror_mode: str = "mirror" # "mirror" (default device plays natively + duplicates) or "all"
        self.master_level: float = 0.0

        self.sample_rate: int = 48000
        self.channels: int = 2
        self.frames_per_buffer: int = 1024
        self.spectrum_bands: List[float] = [0.0] * 20
        self.soloed_device_id: Optional[int] = None

        self.selected_source_index: Optional[int] = None # None means auto-track default
        self.current_source_device_index: Optional[int] = None
        self.loopback_map: Dict[int, dict] = {} # output_idx -> loopback_dev_dict

        self.keep_alive_running: bool = False
        self.keep_alive_stream: Optional[pyaudio.Stream] = None
        self.keep_alive_thread: Optional[threading.Thread] = None

        self.all_input_devices: List[dict] = []
        self.lock = threading.RLock()
        self.init_audio_system()

    def init_audio_system(self):
        with self.lock:
            if self.p is not None:
                try:
                    self.p.terminate()
                except Exception:
                    pass
            self.p = create_audio_interface()
            self.wasapi_info = None
            if IS_WINDOWS and hasattr(self.p, 'get_host_api_info_by_type') and pyaudio is not None and hasattr(pyaudio, 'paWASAPI'):
                try:
                    self.wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                except Exception as e:
                    logger.debug(f"WASAPI info note: {e}")
                    self.wasapi_info = None

            self.refresh_devices()

    def detect_device_category(self, name: str) -> str:
        lower = name.lower()
        if any(k in lower for k in ["buds", "headphone", "headset", "bluetooth", "airpods", "beats", "sony", "wh-", "wf-", "boat", "oneplus", "jbl", "realme", "noise", "wireless", "tws", "earphones", "bose", "sennheiser", "galaxy"]):
            return "bluetooth"
        if any(k in lower for k in ["cable", "virtual", "vb-audio", "line 1", "blackhole", "soundflower", "loopback"]):
            return "virtual"
        if any(k in lower for k in ["speaker", "realtek", "high definition", "macbook", "internal", "built-in", "imac", "audio"]):
            return "speaker"
        if "usb" in lower:
            return "usb"
        return "generic"

    def refresh_devices(self) -> List[dict]:
        """Scans all active output endpoints and loopback/input capture sources."""
        with self.lock:
            if not self.p:
                return []

            dev_count = self.p.get_device_count()
            wasapi_idx = self.wasapi_info['index'] if self.wasapi_info else None

            # Locate default output
            self.default_output_device = None
            if self.wasapi_info:
                default_dev_idx = self.wasapi_info.get('defaultOutputDevice', -1)
                if default_dev_idx >= 0:
                    try:
                        self.default_output_device = self.p.get_device_info_by_index(default_dev_idx)
                    except Exception:
                        pass

            if not self.default_output_device and hasattr(self.p, 'get_default_output_device_info'):
                try:
                    self.default_output_device = self.p.get_default_output_device_info()
                except Exception:
                    pass

            if not self.default_output_device and dev_count > 0:
                for i in range(dev_count):
                    try:
                        d = self.p.get_device_info_by_index(i)
                        if d.get('maxOutputChannels', 0) > 0:
                            self.default_output_device = d
                            break
                    except Exception:
                        pass

            # Detect loopback devices & input sources
            loopback_devices = {}
            input_sources = []
            if hasattr(self.p, 'get_loopback_device_info_generator'):
                try:
                    for loop in self.p.get_loopback_device_info_generator():
                        loopback_devices[loop['name']] = loop
                except Exception as e:
                    logger.warning(f"Error enumerating loopbacks: {e}")
            else:
                for i in range(dev_count):
                    try:
                        d = self.p.get_device_info_by_index(i)
                        if d.get('maxInputChannels', 0) > 0:
                            loopback_devices[d['name']] = d
                            input_sources.append(d)
                    except Exception:
                        pass

            self.all_input_devices = input_sources

            # Match default loopback
            self.default_loopback_device = None
            if self.default_output_device:
                def_name = self.default_output_device['name']
                for lb_name, lb_dev in loopback_devices.items():
                    if def_name in lb_name:
                        self.default_loopback_device = lb_dev
                        break

            # On macOS / Linux: prioritize BlackHole, Soundflower, or Loopback virtual device
            if not self.default_loopback_device:
                for lb_name, lb_dev in loopback_devices.items():
                    if any(k in lb_name.lower() for k in ["blackhole", "soundflower", "loopback"]):
                        self.default_loopback_device = lb_dev
                        break

            if not self.default_loopback_device and loopback_devices:
                self.default_loopback_device = list(loopback_devices.values())[0]

            # Build loopback map: output_index -> loopback_device
            self.loopback_map = {}
            for out_idx in range(dev_count):
                try:
                    d = self.p.get_device_info_by_index(out_idx)
                    if d.get('maxOutputChannels', 0) > 0:
                        if wasapi_idx is not None and d.get('hostApi') != wasapi_idx:
                            continue
                        for lb_name, lb_dev in loopback_devices.items():
                            if d['name'] in lb_name:
                                self.loopback_map[d['index']] = lb_dev
                                break
                except Exception:
                    pass

            # Output devices
            devices = []
            for i in range(dev_count):
                try:
                    d = self.p.get_device_info_by_index(i)
                    if d.get('maxOutputChannels', 0) <= 0:
                        continue
                    if IS_WINDOWS and wasapi_idx is not None and d.get('hostApi') != wasapi_idx:
                        continue

                    is_default = (self.default_output_device and d['index'] == self.default_output_device['index'])
                    cat = self.detect_device_category(d['name'])
                    idx = d['index']

                    if idx not in self.device_configs:
                        initial_vol, initial_mute = get_hardware_system_volume() if is_default else (1.0, False)
                        self.device_configs[idx] = {
                            'volume': initial_vol,
                            'muted': initial_mute,
                            'delay_ms': 0.0,
                            'pan': 0.0,
                            'enabled': True
                        }

                    cfg = self.device_configs[idx]
                    devices.append({
                        'index': d['index'],
                        'name': d['name'],
                        'channels': d['maxOutputChannels'],
                        'sample_rate': int(d['defaultSampleRate']),
                        'is_default': bool(is_default),
                        'category': cat,
                        'volume': cfg['volume'],
                        'muted': cfg['muted'],
                        'delay_ms': cfg['delay_ms'],
                        'pan': cfg['pan'],
                        'enabled': cfg['enabled'],
                        'is_worker_active': (idx in self.workers and self.workers[idx].running)
                    })
                except Exception:
                    continue

            self.all_devices = devices
            return self.all_devices

    def set_device_config(self, index: int, volume: Optional[float] = None, muted: Optional[bool] = None, delay_ms: Optional[float] = None, pan: Optional[float] = None, enabled: Optional[bool] = None):
        with self.lock:
            if index not in self.device_configs:
                self.device_configs[index] = {'volume': 1.0, 'muted': False, 'delay_ms': 0.0, 'pan': 0.0, 'enabled': True}
            cfg = self.device_configs[index]
            if volume is not None:
                cfg['volume'] = max(0.0, min(float(volume), 2.0))
            if muted is not None:
                cfg['muted'] = bool(muted)
            if delay_ms is not None:
                cfg['delay_ms'] = max(0.0, min(float(delay_ms), 1000.0))
            if pan is not None:
                cfg['pan'] = max(-1.0, min(float(pan), 1.0))
            if enabled is not None:
                cfg['enabled'] = bool(enabled)

            # If default device, sync with system master volume (Windows or macOS)
            if self.default_output_device and index == self.default_output_device['index']:
                sync_hardware_system_volume(volume=volume, muted=muted)

            # Update active worker if running
            if index in self.workers:
                worker = self.workers[index]
                worker.update_settings(
                    volume=cfg['volume'] * (0.0 if self.master_muted else self.master_volume),
                    muted=cfg['muted'],
                    delay_ms=cfg['delay_ms'],
                    pan=cfg['pan']
                )

                # If toggled off during broadcast, stop worker
                if enabled is False and worker.running:
                    worker.stop()
                    del self.workers[index]

            # If enabled during broadcast, start worker
            if enabled is True and self.is_broadcasting and index not in self.workers:
                self._start_worker_for_device(index)

    def set_master_config(self, volume: Optional[float] = None, muted: Optional[bool] = None, mode: Optional[str] = None):
        with self.lock:
            if volume is not None:
                self.master_volume = max(0.0, min(float(volume), 2.0))
            if muted is not None:
                self.master_muted = bool(muted)
            if mode in ["mirror", "all"]:
                self.mirror_mode = mode

            # propagate to all workers
            for idx, worker in self.workers.items():
                cfg = self.device_configs.get(idx, {})
                worker.update_settings(
                    volume=cfg.get('volume', 1.0) * (0.0 if self.master_muted else self.master_volume)
                )

    def _start_worker_for_device(self, dev_index: int):
        dev_info = None
        for d in self.all_devices:
            if d['index'] == dev_index:
                dev_info = d
                break
        if not dev_info:
            return

        # Never duplicate capture source back into itself to prevent feedback loop / device collision!
        if dev_index == self.current_source_device_index:
            logger.info(f"Skipping worker duplicate on capture source '{dev_info['name']}'.")
            return

        cfg = self.device_configs.get(dev_index, {})
        worker = OutputDeviceWorker(
            p_inst=self.p,
            device_info=dev_info,
            target_sample_rate=self.sample_rate,
            channels=self.channels,
            frames_per_buffer=self.frames_per_buffer,
            volume=cfg.get('volume', 1.0) * (0.0 if self.master_muted else self.master_volume),
            muted=cfg.get('muted', False),
            delay_ms=cfg.get('delay_ms', 0.0),
            pan=cfg.get('pan', 0.0)
        )
        if worker.open_stream():
            worker.start()
            self.workers[dev_index] = worker
        else:
            logger.warning(f"Could not open output stream for '{dev_info['name']}'")

    def _start_keep_alive(self, dev_index: int):
        """Starts a background silence feeder stream on source device to guarantee active clock ticks."""
        self._stop_keep_alive()
        self.keep_alive_running = True
        silence = np.zeros((1024, self.channels), dtype=np.float32).tobytes()

        try:
            self.keep_alive_stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                output_device_index=dev_index,
                frames_per_buffer=1024
            )
            # Write 2 frames of silence to prime driver clock immediately
            for _ in range(2):
                self.keep_alive_stream.write(silence)
        except Exception as e:
            logger.debug(f"Keep-alive feeder init note on {dev_index}: {e}")
            self.keep_alive_stream = None
            return

        def _feeder():
            while self.keep_alive_running and self.keep_alive_stream:
                try:
                    self.keep_alive_stream.write(silence)
                    time.sleep(0.015)
                except Exception:
                    break

        self.keep_alive_thread = threading.Thread(target=_feeder, name="KeepAliveFeeder", daemon=True)
        self.keep_alive_thread.start()

    def _stop_keep_alive(self):
        """Stops the silence feeder stream cleanly."""
        self.keep_alive_running = False
        if self.keep_alive_thread and self.keep_alive_thread.is_alive():
            try:
                self.keep_alive_thread.join(timeout=0.3)
            except Exception:
                pass
        self.keep_alive_thread = None

        try:
            if self.keep_alive_stream:
                self.keep_alive_stream.stop_stream()
                self.keep_alive_stream.close()
        except Exception:
            pass
        self.keep_alive_stream = None

    def set_source_device(self, dev_index: Optional[int]):
        """Sets the audio capture source line and dynamically hot-switches if broadcasting."""
        with self.lock:
            self.selected_source_index = dev_index
            if self.is_broadcasting:
                logger.info(f"Hot-switching capture source to: {dev_index}")
                self.stop_broadcast()
                time.sleep(0.1)
                self.start_broadcast()

    def _recover_capture_stream(self):
        """Auto-recovers when Windows audio switches lines or invalidates stream."""
        with self.lock:
            try:
                if self.capture_stream:
                    try:
                        self.capture_stream.stop_stream()
                        self.capture_stream.close()
                    except Exception:
                        pass
                    self.capture_stream = None

                self.refresh_devices()
                src_dev = None
                if self.selected_source_index is not None:
                    for d in self.all_devices:
                        if d['index'] == self.selected_source_index:
                            src_dev = d
                            break
                if not src_dev:
                    src_dev = self.default_output_device or (self.all_devices[0] if self.all_devices else None)

                if src_dev:
                    lb = self.loopback_map.get(src_dev['index'])
                    if lb:
                        self._start_keep_alive(src_dev['index'])
                        self.capture_stream = self.p.open(
                            format=pyaudio.paFloat32,
                            channels=self.channels,
                            rate=self.sample_rate,
                            input=True,
                            input_device_index=lb['index'],
                            frames_per_buffer=self.frames_per_buffer
                        )
                        logger.info(f"Auto-recovery successful: loopback re-attached to {lb['name']}")
            except Exception as rec_err:
                logger.debug(f"Recovery attempt error: {rec_err}")

    def start_broadcast(self) -> bool:
        """Starts loopback/input capture and initiates multi-device streaming workers."""
        with self.lock:
            if self.is_broadcasting:
                return True

            self.refresh_devices()

            # Determine source capture device
            src_dev = None
            if self.selected_source_index is not None:
                for d in self.all_devices:
                    if d['index'] == self.selected_source_index:
                        src_dev = d
                        break
                if not src_dev:
                    for d in self.all_input_devices:
                        if d['index'] == self.selected_source_index:
                            src_dev = d
                            break

            if not src_dev:
                src_dev = self.default_output_device

            if not src_dev and self.all_devices:
                src_dev = self.all_devices[0]

            if not src_dev and self.all_input_devices:
                src_dev = self.all_input_devices[0]

            if not src_dev:
                logger.error("No audio device available for capture.")
                return False

            self.current_source_device_index = src_dev['index']

            # Match loopback device
            lb = self.loopback_map.get(src_dev['index'])
            if not lb and hasattr(self.p, 'get_loopback_device_info_generator'):
                for loop in self.p.get_loopback_device_info_generator():
                    if src_dev['name'] in loop['name']:
                        lb = loop
                        break

            # If src_dev has input channels, it can be captured directly (macOS BlackHole, mic, etc.)
            if not lb and src_dev.get('maxInputChannels', 0) > 0:
                lb = src_dev

            if not lb:
                lb = self.default_loopback_device

            if not lb and self.all_input_devices:
                lb = self.all_input_devices[0]

            if not lb:
                logger.error(f"No loopback capture device found for '{src_dev['name']}'")
                return False

            logger.info(f"Attaching audio capture to: {lb['name']} (index {lb['index']})")

            self.sample_rate = int(lb.get('defaultSampleRate', 48000))
            self.channels = min(2, max(1, lb.get('maxInputChannels', 2)))

            # Start keep-alive feeder on capture source to guarantee active driver clock (prevents VAC hanging on Windows)
            if IS_WINDOWS:
                self._start_keep_alive(src_dev['index'])

            try:
                self.capture_stream = self.p.open(
                    format=pyaudio.paFloat32 if hasattr(pyaudio, 'paFloat32') else 1,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=lb['index'],
                    frames_per_buffer=self.frames_per_buffer
                )
            except Exception as e:
                logger.error(f"Failed to open capture stream: {e}")
                self._stop_keep_alive()
                return False

            # Start workers for all enabled devices (skipping capture source if in mirror mode)
            self.workers.clear()
            for dev in self.all_devices:
                idx = dev['index']
                cfg = self.device_configs.get(idx, {})
                if cfg.get('enabled', True):
                    self._start_worker_for_device(idx)

            self.is_broadcasting = True
            self.capture_thread = threading.Thread(target=self._capture_loop, name="CaptureThread", daemon=True)
            self.capture_thread.start()
            logger.info(f"Broadcasting started successfully from '{src_dev['name']}' to active targets.")
            return True

    def _capture_loop(self):
        """Continuously captures system audio and broadcasts to active device workers."""
        while self.is_broadcasting and self.capture_stream:
            try:
                raw_data = self.capture_stream.read(self.frames_per_buffer, exception_on_overflow=False)
                if not raw_data:
                    continue

                # Convert to numpy float32
                chunk = np.frombuffer(raw_data, dtype=np.float32)
                if self.channels == 2:
                    chunk = chunk.reshape(-1, 2)
                else:
                    chunk = np.column_stack((chunk, chunk))

                # Master level calculation
                rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
                self.master_level = min(1.0, rms * 3.5)

                # Real-time FFT spectrum analyzer (20 logarithmic frequency bands)
                if len(chunk) > 32:
                    try:
                        mono = np.mean(chunk, axis=1)
                        fft_vals = np.abs(np.fft.rfft(mono))
                        n_bins = len(fft_vals)
                        edges = np.logspace(np.log10(1), np.log10(n_bins - 1), num=21).astype(int)
                        bands = []
                        for bi in range(20):
                            s = edges[bi]
                            e = max(s + 1, edges[bi + 1])
                            val = float(np.mean(fft_vals[s:e]))
                            bands.append(round(min(1.0, val / 12.0), 3))
                        self.spectrum_bands = bands
                    except Exception:
                        pass

                # Dispatch copy to each active device worker (with Solo support)
                solo_id = self.soloed_device_id
                for dev_idx, worker in list(self.workers.items()):
                    if worker.running:
                        if solo_id is not None and dev_idx != solo_id:
                            # Silenced when another device is in solo mode
                            silence = np.zeros_like(chunk)
                            worker.push_audio(silence)
                        else:
                            worker.push_audio(chunk.copy())

            except Exception as e:
                if self.is_broadcasting:
                    logger.warning(f"Capture stream notice ({e}). Auto-recovering...")
                    time.sleep(0.15)
                    self._recover_capture_stream()

        self.master_level = 0.0
        self.spectrum_bands = [0.0] * 20

    def stop_broadcast(self):
        """Stops audio capture and terminates all device worker streams safely."""
        with self.lock:
            if not self.is_broadcasting:
                return
            self.is_broadcasting = False

        # Allow capture loop to exit gracefully without mutex contention
        if self.capture_thread and self.capture_thread.is_alive():
            try:
                self.capture_thread.join(timeout=0.3)
            except Exception:
                pass
        self.capture_thread = None

        with self.lock:
            # Stop keep-alive clock feeder
            self._stop_keep_alive()

            # Close capture stream safely
            try:
                if self.capture_stream:
                    try:
                        self.capture_stream.stop_stream()
                    except Exception:
                        pass
                    try:
                        self.capture_stream.close()
                    except Exception:
                        pass
                    self.capture_stream = None
            except Exception as e:
                logger.warning(f"Error closing capture stream: {e}")

            # Signal workers to stop and safely close streams
            for worker in list(self.workers.values()):
                worker.stop()
            for worker in list(self.workers.values()):
                if worker.is_alive():
                    try:
                        worker.join(timeout=0.3)
                    except Exception:
                        pass
                worker.close_stream()
            self.workers.clear()
            self.master_level = 0.0
            logger.info("Broadcasting stopped.")

    def play_test_tone(self, device_index: Optional[int] = None, duration_sec: float = 0.8):
        """Generates a pleasant harmonic stereo chime on a specific device or all devices."""
        def _tone_runner():
            sr = 48000
            t = np.linspace(0, duration_sec, int(sr * duration_sec), False)
            env = np.exp(-4.0 * t)
            left_ch = 0.25 * env * np.sin(2 * np.pi * 523.25 * t)
            right_ch = 0.25 * env * np.sin(2 * np.pi * 659.25 * t)
            stereo = np.column_stack((left_ch, right_ch)).astype(np.float32)

            target_indices = [device_index] if device_index is not None else [d['index'] for d in self.all_devices]

            for idx in target_indices:
                # If a worker is actively running on this device, push into worker
                if idx in self.workers and self.workers[idx].running:
                    # Push tone in chunks
                    chunk_sz = 1024
                    for offset in range(0, len(stereo), chunk_sz):
                        self.workers[idx].push_audio(stereo[offset:offset+chunk_sz].copy())
                    continue

                # Otherwise open temporary stream
                try:
                    s = self.p.open(
                        format=pyaudio.paFloat32,
                        channels=2,
                        rate=sr,
                        output=True,
                        output_device_index=idx,
                        frames_per_buffer=1024
                    )
                    s.write(stereo.tobytes())
                    s.stop_stream()
                    s.close()
                except Exception as e:
                    logger.warning(f"Could not play test tone on device {idx}: {e}")

        threading.Thread(target=_tone_runner, daemon=True).start()

    def toggle_solo(self, device_id: int) -> Optional[int]:
        with self.lock:
            if self.soloed_device_id == device_id:
                self.soloed_device_id = None
            else:
                self.soloed_device_id = device_id
            return self.soloed_device_id

    def apply_preset(self, preset_name: str) -> dict:
        with self.lock:
            if preset_name == "party":
                # Enable all devices, 100% volume, 0ms delay
                for d in self.all_devices:
                    self.set_device_config(d['index'], volume=1.0, muted=False, enabled=True)
            elif preset_name == "cinema":
                # Set delay compensation for Bluetooth devices to ~120ms
                for d in self.all_devices:
                    if d['category'] == 'bluetooth':
                        self.set_device_config(d['index'], volume=1.0, muted=False, delay_ms=120.0, enabled=True)
                    else:
                        self.set_device_config(d['index'], volume=0.8, muted=False, delay_ms=0.0, enabled=True)
            elif preset_name == "balanced":
                # Master 100%, each device 85%, 0 delay
                self.set_master_config(volume=1.0, muted=False)
                for d in self.all_devices:
                    self.set_device_config(d['index'], volume=0.85, muted=False, delay_ms=0.0, enabled=True)
            return self.get_status()

    def get_meter_levels(self) -> dict:
        """Returns real-time VU meter levels, 20-band FFT spectrum, and solo state."""
        device_levels = {}
        for idx, worker in self.workers.items():
            device_levels[idx] = round(worker.current_level, 3)

        # For default output device in mirror mode, pass master captured level
        if self.default_output_device and self.is_broadcasting:
            def_idx = self.default_output_device['index']
            if def_idx not in device_levels:
                device_levels[def_idx] = round(self.master_level, 3)

        return {
            'is_broadcasting': self.is_broadcasting,
            'master_level': round(self.master_level, 3),
            'device_levels': device_levels,
            'spectrum': self.spectrum_bands,
            'soloed_device_id': self.soloed_device_id
        }

    def get_status(self) -> dict:
        """Returns full snapshot of audio router state and devices."""
        self.refresh_devices()
        return {
            'is_broadcasting': self.is_broadcasting,
            'master_volume': self.master_volume,
            'master_muted': self.master_muted,
            'mirror_mode': self.mirror_mode,
            'sample_rate': self.sample_rate,
            'default_output': self.default_output_device['name'] if self.default_output_device else None,
            'default_loopback': self.default_loopback_device['name'] if self.default_loopback_device else None,
            'selected_source_index': self.selected_source_index,
            'current_source_device_index': self.current_source_device_index,
            'devices': self.all_devices,
            'input_devices': [{'index': d['index'], 'name': d['name']} for d in self.all_input_devices],
            'soloed_device_id': self.soloed_device_id,
            'platform': 'darwin' if IS_MAC else ('win32' if IS_WINDOWS else sys.platform),
            'backend': BACKEND_NAME
        }


# Global engine instance
audio_engine = AudioRouter()
