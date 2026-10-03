"""
SoundSync Multi-Out - Flask Web Server & API
Provides REST endpoints and Server-Sent Events (SSE) for the frontend mixer UI.
"""

import sys
import os
import json
import time
from flask import Flask, render_template, request, jsonify, Response
try:
    from .audio_engine import audio_engine
except ImportError:
    from audio_engine import audio_engine

if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(BASE_DIR, 'templates')
static_dir = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    try:
        return jsonify({
            'success': True,
            'data': audio_engine.get_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/devices/refresh', methods=['POST'])
def refresh_devices():
    try:
        devices = audio_engine.refresh_devices()
        return jsonify({
            'success': True,
            'devices': devices,
            'status': audio_engine.get_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broadcast/start', methods=['POST'])
def start_broadcast():
    try:
        success = audio_engine.start_broadcast()
        return jsonify({
            'success': success,
            'is_broadcasting': audio_engine.is_broadcasting,
            'status': audio_engine.get_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broadcast/stop', methods=['POST'])
def stop_broadcast():
    try:
        audio_engine.stop_broadcast()
        return jsonify({
            'success': True,
            'is_broadcasting': False,
            'status': audio_engine.get_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/master', methods=['POST'])
def update_master():
    try:
        data = request.json or {}
        volume = data.get('volume')
        muted = data.get('muted')
        mode = data.get('mode')
        audio_engine.set_master_config(volume=volume, muted=muted, mode=mode)
        return jsonify({'success': True, 'status': audio_engine.get_status()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<int:dev_id>', methods=['POST'])
def update_device(dev_id):
    try:
        data = request.json or {}
        volume = data.get('volume')
        muted = data.get('muted')
        delay_ms = data.get('delay_ms')
        pan = data.get('pan')
        enabled = data.get('enabled')

        audio_engine.set_device_config(
            index=dev_id,
            volume=volume,
            muted=muted,
            delay_ms=delay_ms,
            pan=pan,
            enabled=enabled
        )
        return jsonify({'success': True, 'status': audio_engine.get_status()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<int:dev_id>/solo', methods=['POST'])
def solo_device(dev_id):
    try:
        solo_id = audio_engine.toggle_solo(dev_id)
        return jsonify({
            'success': True,
            'soloed_device_id': solo_id,
            'status': audio_engine.get_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preset/<preset_name>', methods=['POST'])
def apply_preset(preset_name):
    try:
        status = audio_engine.apply_preset(preset_name)
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/source/select', methods=['POST'])
def select_source():
    try:
        data = request.json or {}
        src_id = data.get('source_device_index')
        audio_engine.set_source_device(src_id)
        return jsonify({'success': True, 'status': audio_engine.get_status()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test_tone', methods=['POST'])
def test_tone():
    try:
        data = request.json or {}
        device_index = data.get('device_index') # None means all
        audio_engine.play_test_tone(device_index=device_index)
        return jsonify({'success': True, 'message': 'Test tone triggered'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/meters', methods=['GET'])
def get_meters():
    try:
        return jsonify(audio_engine.get_meter_levels())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/meter_stream')
def meter_stream():
    """SSE endpoint streaming live audio meters 25 times per second."""
    def event_generator():
        while True:
            try:
                data = json.dumps(audio_engine.get_meter_levels())
                yield f"data: {data}\n\n"
                time.sleep(0.04) # ~25 FPS
            except Exception:
                break

    return Response(event_generator(), mimetype='text/event-stream')


def start_server(host='127.0.0.1', port=8765, debug=False):
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == '__main__':
    start_server()
