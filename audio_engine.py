"""
SoundSync Multi-Out - Audio Engine
High-performance multi-device audio capture and broadcast engine for Windows.
Utilizes WASAPI Loopback to capture system audio and routes it simultaneously
to multiple output endpoints (e.g., multiple Bluetooth headphones/speakers)
with independent volume, mute, delay sync compensation, and real-time VU metering.
"""

import time
import math
import queue
import threading
import logging
from typing import Dict, List, Optional, Any
import numpy as np
import pyaudiowpatch as pyaudio

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AudioEngine")


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

    def run(self):
        logger.info(f"Starting output stream for '{self.device_name}' (idx {self.device_index}, sr {self.sample_rate}, ch {self.channels})")
        try:
            self.stream = self.p_inst.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                output_device_index=self.device_index,
                frames_per_buffer=self.frames_per_buffer
            )
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"Failed to open audio stream for {self.device_name}: {e}")
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
                self.stream.write(data_bytes)
            except Exception as e:
                logger.warning(f"Write error on {self.device_name}: {e}")
                time.sleep(0.01)

        # Cleanup
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        except Exception:
            pass
        logger.info(f"Output stream stopped for '{self.device_name}'")

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

        self.lock = threading.RLock()
        self.init_audio_system()

    def init_audio_system(self):
        with self.lock:
            if self.p is not None:
                try:
                    self.p.terminate()
                except Exception:
                    pass
            self.p = pyaudio.PyAudio()
            try:
                self.wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            except Exception as e:
                logger.error(f"Error accessing WASAPI: {e}")
                self.wasapi_info = None

            self.refresh_devices()

    def detect_device_category(self, name: str) -> str:
        lower = name.lower()
        if any(k in lower for k in ["buds", "headphone", "headset", "bluetooth", "airpods", "sony", "wh-", "wf-", "boat", "oneplus", "jbl", "realme", "noise", "wireless", "tws", "earphones"]):
            return "bluetooth"
        if any(k in lower for k in ["cable", "virtual", "vb-audio", "line 1"]):
            return "virtual"
        if any(k in lower for k in ["speaker", "realtek", "high definition", "audio"]):
            return "speaker"
        if "usb" in lower:
            return "usb"
        return "generic"

    def refresh_devices(self) -> List[dict]:
        """Scans all active WASAPI output endpoints and loopback devices."""
        with self.lock:
            if not self.p or not self.wasapi_info:
                return []

            dev_count = self.p.get_device_count()
            wasapi_idx = self.wasapi_info['index']

            default_dev_idx = self.wasapi_info.get('defaultOutputDevice', -1)
            self.default_output_device = None
            if default_dev_idx >= 0:
                try:
                    self.default_output_device = self.p.get_device_info_by_index(default_dev_idx)
                except Exception:
                    pass

            # Detect loopback devices
            loopback_devices = {}
            try:
                for loop in self.p.get_loopback_device_info_generator():
                    loopback_devices[loop['name']] = loop
            except Exception as e:
                logger.warning(f"Error enumerating loopbacks: {e}")

            # Match default loopback
            self.default_loopback_device = None
            if self.default_output_device:
                def_name = self.default_output_device['name']
                for lb_name, lb_dev in loopback_devices.items():
                    if def_name in lb_name:
                        self.default_loopback_device = lb_dev
                        break
            if not self.default_loopback_device and loopback_devices:
                self.default_loopback_device = list(loopback_devices.values())[0]

            # Output devices
            devices = []
            for i in range(dev_count):
                try:
                    d = self.p.get_device_info_by_index(i)
                    if d['hostApi'] == wasapi_idx and d['maxOutputChannels'] > 0:
                        is_default = (self.default_output_device and d['index'] == self.default_output_device['index'])
                        cat = self.detect_device_category(d['name'])
                        
                        idx = d['index']
                        if idx not in self.device_configs:
                            # If default device, sync from Windows volume
                            initial_vol = 1.0
                            initial_mute = False
                            if is_default:
                                try:
                                    from pycaw.pycaw import AudioUtilities
                                    spk = AudioUtilities.GetSpeakers()
                                    initial_vol = round(spk.volume_percent / 100.0, 2)
                                    initial_mute = bool(spk.EndpointVolume.GetMute())
                                except Exception:
                                    pass

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

            # If default device, sync with Windows Endpoint Master Volume
            if self.default_output_device and index == self.default_output_device['index']:
                try:
                    from pycaw.pycaw import AudioUtilities
                    spk = AudioUtilities.GetSpeakers()
                    if volume is not None:
                        spk.volume_percent = max(0.0, min(float(volume), 1.0)) * 100.0
                    if muted is not None:
                        spk.EndpointVolume.SetMute(1 if muted else 0, None)
                except Exception as e:
                    logger.debug(f"Hardware volume sync error: {e}")

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

        is_default = dev_info['is_default']
        # In mirror mode, Windows already plays audio to default device natively.
        # So we skip default device worker in mirror mode to prevent double audio/echo!
        if self.mirror_mode == "mirror" and is_default:
            logger.info(f"Mirror mode active: Default output '{dev_info['name']}' plays natively. Skipping worker duplicate.")
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
        worker.start()
        self.workers[dev_index] = worker

    def start_broadcast(self) -> bool:
        """Starts WASAPI loopback capture and initiates multi-device streaming workers."""
        with self.lock:
            if self.is_broadcasting:
                return True

            self.refresh_devices()
            if not self.default_loopback_device:
                logger.error("No loopback device found for broadcast capture.")
                return False

            lb = self.default_loopback_device
            logger.info(f"Attaching WASAPI loopback capture to: {lb['name']} (index {lb['index']})")

            self.sample_rate = int(lb['defaultSampleRate'])
            self.channels = min(2, lb['maxInputChannels'])

            try:
                self.capture_stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=lb['index'],
                    frames_per_buffer=self.frames_per_buffer
                )
            except Exception as e:
                logger.error(f"Failed to open loopback capture stream: {e}")
                return False

            # Start workers for all enabled devices
            self.workers.clear()
            for dev in self.all_devices:
                idx = dev['index']
                cfg = self.device_configs.get(idx, {})
                if cfg.get('enabled', True):
                    self._start_worker_for_device(idx)

            self.is_broadcasting = True
            self.capture_thread = threading.Thread(target=self._capture_loop, name="LoopbackCaptureThread", daemon=True)
            self.capture_thread.start()
            logger.info("Broadcasting started successfully across all target devices.")
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

                # Dispatch copy to each active device worker
                for worker in list(self.workers.values()):
                    if worker.running:
                        worker.push_audio(chunk.copy())

            except Exception as e:
                if self.is_broadcasting:
                    logger.warning(f"Loopback read exception: {e}")
                    time.sleep(0.01)

        self.master_level = 0.0

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

        with self.lock:
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

            # Signal workers to stop
            for worker in list(self.workers.values()):
                worker.stop()
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

    def get_meter_levels(self) -> dict:
        """Returns real-time VU meter levels for master and each device."""
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
            'device_levels': device_levels
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
            'devices': self.all_devices
        }


# Global engine instance
audio_engine = AudioRouter()
