#!/usr/bin/env python3
"""
Simple Flask app that subscribes to an MQTT topic and serves
the last JPEG message received on that topic.

Environment variables:
- MQTT_BROKER_HOST (default: localhost)
- MQTT_BROKER_PORT (default: 1883)
- MQTT_USERNAME (optional)
- MQTT_PASSWORD (optional)
- MQTT_CLIENT_CERT (optional, path to client certificate PEM file)
- MQTT_CLIENT_KEY (optional, path to client private key PEM file)
- MQTT_CA_CERT (optional, path to CA certificate PEM file)
- MQTT_TOPIC (default: frigate/hofcam1/person)
- HTTP_HOST (default: 0.0.0.0)
- HTTP_PORT (default: 8080)
- IMAGE_REFRESH_MS (default: 2000)  # used by the web page JS auto-reload
"""

import os
import logging
import threading
import time
import base64
import requests
import queue

from flask import (
    Flask,
    Response,
    render_template_string,
    jsonify,
    stream_with_context,
    request,
)
import paho.mqtt.client as mqtt

# Configuration from env
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)
# Default to the snapshot topic which contains raw JPEG payloads.
# Can be overridden with the MQTT_TOPIC environment variable.
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "frigate/hofcam1/person/snapshot")

# MQTT TLS/Certificate-based authentication
MQTT_CLIENT_CERT = os.getenv("MQTT_CLIENT_CERT", None)
MQTT_CLIENT_KEY = os.getenv("MQTT_CLIENT_KEY", None)
MQTT_CA_CERT = os.getenv("MQTT_CA_CERT", None)

HTTP_HOST = os.getenv("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
IMAGE_REFRESH_MS = int(os.getenv("IMAGE_REFRESH_MS", "2000"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
_log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=_log_level, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(_log_level)

app = Flask(__name__)

# Shared state for last image
# Store latest image for each (cam, object): {(cam, object): (image_bytes, timestamp)}
_latest_images = {}
_lock = threading.RLock()

# SSE: list of queues for connected clients
_sse_clients = []
_sse_clients_lock = threading.Lock()


def store_image_for_topic(candidate_bytes: bytes, cam: str, obj: str) -> bool:
    """
    Store the image for (cam, obj) if candidate_bytes is a jpeg (raw, base64, or URL).
    Return True if stored, False otherwise.
    """
    if not candidate_bytes:
        return False

    # If the payload is a URL (http/https), fetch the image
    try:
        as_str = (
            candidate_bytes.decode("utf-8")
            if isinstance(candidate_bytes, bytes)
            else str(candidate_bytes)
        )
    except Exception:
        as_str = None
    if as_str and as_str.strip().lower().startswith("http"):
        img = fetch_jpeg_from_url(as_str.strip())
        if img and img[:3] == b"\xff\xd8\xff":
            with _lock:
                _latest_images[(cam, obj)] = (img, time.time())
            logger.info(
                "Stored JPEG fetched from URL for %s/%s (size=%d)", cam, obj, len(img)
            )
            notify_sse_clients()
            return True
        else:
            logger.warning("URL did not yield a valid JPEG: %s", as_str)
            return False

    # If the payload already looks like JPEG bytes:
    if candidate_bytes[:3] == b"\xff\xd8\xff":
        with _lock:
            _latest_images[(cam, obj)] = (candidate_bytes, time.time())
        logger.info(
            "Stored raw JPEG image for %s/%s (size=%d)", cam, obj, len(candidate_bytes)
        )
        notify_sse_clients()
        return True

    # Try base64 decode (payload may be str or bytes)
    try:
        if isinstance(candidate_bytes, str):
            cand = candidate_bytes.encode("utf-8")
        else:
            cand = candidate_bytes
        decoded = base64.b64decode(cand, validate=True)
        if decoded[:3] == b"\xff\xd8\xff":
            with _lock:
                _latest_images[(cam, obj)] = (decoded, time.time())
            logger.info(
                "Stored base64-decoded JPEG image for %s/%s (size=%d)",
                cam,
                obj,
                len(decoded),
            )
            notify_sse_clients()
            return True
    except Exception:
        pass

    # Not a JPEG we recognize
    return False


# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(
            "Connected to MQTT broker %s:%d", MQTT_BROKER_HOST, MQTT_BROKER_PORT
        )
        client.subscribe(MQTT_TOPIC)
        logger.info("Subscribed to topic: %s", MQTT_TOPIC)
    else:
        logger.error("Failed to connect to MQTT broker, rc=%s", rc)


def on_message(client, userdata, msg):
    logger.debug("MQTT message on %s (len=%d)", msg.topic, len(msg.payload))
    # Parse topic: frigate/<cam>/<object>/snapshot
    parts = msg.topic.split("/")
    if len(parts) == 4 and parts[0] == "frigate" and parts[3] == "snapshot":
        cam = parts[1]
        obj = parts[2]
        ok = store_image_for_topic(msg.payload, cam, obj)
        if not ok:
            logger.warning(
                "Received message on %s but it is not a recognizable JPEG", msg.topic
            )
    else:
        logger.debug(
            "Ignoring message on topic %s (does not match frigate/<cam>/<object>/snapshot)",
            msg.topic,
        )


def start_mqtt_client():
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # TLS/Certificate-based authentication
    if MQTT_CLIENT_CERT and MQTT_CLIENT_KEY:
        logger.info("Configuring MQTT client for certificate-based authentication")
        tls_kwargs = {
            "ca_certs": MQTT_CA_CERT if MQTT_CA_CERT else None,
            "certfile": MQTT_CLIENT_CERT,
            "keyfile": MQTT_CLIENT_KEY,
        }
        # Remove None values for compatibility
        tls_kwargs = {k: v for k, v in tls_kwargs.items() if v is not None}
        client.tls_set(**tls_kwargs)
        # Optionally, you can enforce certificate validation here
        client.tls_insecure_set(False)
    elif MQTT_CA_CERT:
        logger.info("Configuring MQTT client for TLS server authentication only")
        client.tls_set(ca_certs=MQTT_CA_CERT)
        client.tls_insecure_set(False)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    except Exception as e:
        logger.error(
            "Could not connect to MQTT broker %s:%d: %s",
            MQTT_BROKER_HOST,
            MQTT_BROKER_PORT,
            e,
        )
        raise

    # Start network loop in a background thread
    client.loop_start()
    return client


@app.route("/")
def index():
    # Gallery page: show latest images grouped by camera/object
    html = """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8"/>
        <title>Frigate MQTT Gallery</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 1rem; }
          .meta { margin-top: 0.5rem; color: #666; }
          .cam-group { margin-bottom: 2rem; }
          .cam-title { font-size: 1.2em; font-weight: bold; margin-bottom: 0.5em; }
          .object-row { display: flex; flex-wrap: wrap; gap: 1em; }
          .object-card { border: 1px solid #ccc; padding: 0.5em; border-radius: 4px; background: #fafafa; }
          .object-card img { max-width: 200px; max-height: 150px; display: block; cursor: pointer; transition: box-shadow 0.2s; }
          .object-label { font-size: 0.95em; color: #333; margin-top: 0.2em; }
          .fullscreen-img {
            position: fixed !important;
            top: 0; left: 0; right: 0; bottom: 0;
            width: 100vw !important;
            height: 100vh !important;
            max-width: 100vw !important;
            max-height: 100vh !important;
            object-fit: contain;
            background: #000;
            z-index: 9999;
            margin: 0 !important;
            display: block;
            box-shadow: 0 0 0 9999px rgba(0,0,0,0.8);
          }
        </style>
      </head>
      <body>
        <h1 id="page-title">Frigate MQTT Gallery</h1>
        <button id="kiosk-btn" style="margin-bottom:1rem;">Enter Kiosk Mode</button>
        <div id="gallery"></div>
        <div class="meta" id="meta-bar">
          Subscribed topic: <code>{{topic}}</code>
        </div>
        <script>
        // Kiosk mode logic
        const kioskBtn = document.getElementById('kiosk-btn');
        let kioskActive = false;
        function setKioskMode(on) {
          kioskActive = on;
          document.body.classList.toggle('kiosk', on);
          document.getElementById('page-title').style.display = on ? 'none' : '';
          document.getElementById('meta-bar').style.display = on ? 'none' : '';
          kioskBtn.textContent = on ? 'Exit Kiosk Mode' : 'Enter Kiosk Mode';
          if (on) {
            if (document.documentElement.requestFullscreen) {
              document.documentElement.requestFullscreen();
            }
          } else {
            if (document.fullscreenElement) {
              document.exitFullscreen();
            }
          }
        }
        kioskBtn.onclick = function() {
          setKioskMode(!kioskActive);
        };
        document.addEventListener('fullscreenchange', function() {
          if (!document.fullscreenElement && kioskActive) {
            setKioskMode(false);
          }
        });

        // Double-click-to-fullscreen logic for gallery images
        function setupFullscreenOnImages() {
          document.querySelectorAll('#gallery img').forEach(img => {
            img.ondblclick = function(e) {
              if (img.classList.contains('fullscreen-img')) {
                img.classList.remove('fullscreen-img');
                document.body.style.overflow = '';
              } else {
                // Remove fullscreen from any other image
                document.querySelectorAll('.fullscreen-img').forEach(el => el.classList.remove('fullscreen-img'));
                img.classList.add('fullscreen-img');
                document.body.style.overflow = 'hidden';
              }
            };
          });
          // Exit fullscreen on ESC key
          document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
              document.querySelectorAll('.fullscreen-img').forEach(el => el.classList.remove('fullscreen-img'));
              document.body.style.overflow = '';
            }
          });
        }

        async function fetchGallery() {
          const resp = await fetch('/gallery');
          const data = await resp.json();
          const cams = {};
          let latestKey = null;
          let latestTs = -1;
          if (data.latest) {
            latestKey = data.latest.cam + '|' + data.latest.obj;
            latestTs = data.latest.ts;
          }
          for (const entry of data.images) {
            if (!cams[entry.cam]) cams[entry.cam] = [];
            cams[entry.cam].push(entry);
          }
          let html = '';
          for (const cam in cams) {
            html += `<div class="cam-group"><div class="cam-title">Camera: <b>${cam}</b></div><div class="object-row">`;
            for (const entry of cams[cam]) {
              const isLatest = latestKey && (entry.cam + '|' + entry.obj) === latestKey && entry.ts === latestTs;
              html += `<div class="object-card${isLatest ? ' latest-image' : ''}">
                <img src="/image/${encodeURIComponent(entry.cam)}/${encodeURIComponent(entry.obj)}.jpg?ts=${entry.ts}" alt="No image" />
                <div class="object-label">Object: <b>${entry.obj}</b><br><span style='font-size:0.85em;color:#888'>${new Date(entry.ts*1000).toLocaleString()}</span></div>
              </div>`;
            }
            html += "</div></div>";
          }
          document.getElementById('gallery').innerHTML = html || "<i>No images yet.</i>";
          setupFullscreenOnImages();
        }
        fetchGallery();
        const evtSource = new EventSource('/events');
        evtSource.onmessage = function(event) {
          fetchGallery();
        };
        </script>
        <style>
        body.kiosk {
          background: #000;
        }
        body.kiosk #kiosk-btn,
        body.kiosk #page-title,
        body.kiosk #meta-bar {
          display: none !important;
        }
        body.kiosk #gallery {
          margin-top: 0 !important;
        }
        .latest-image {
          border: 4px solid red !important;
          box-sizing: border-box;
        }
        </style>
      </body>
    </html>
    """
    return render_template_string(html, topic=MQTT_TOPIC)
    return render_template_string(
        html, topic=MQTT_TOPIC, ts=ts, human_ts=human_ts, refresh_ms=IMAGE_REFRESH_MS
    )


@app.route("/image/<cam>/<obj>.jpg")
def image(cam, obj):
    with _lock:
        key = (cam, obj)
        entry = _latest_images.get(key)
        if not entry:
            return Response(status=204)
        img, ts = entry
    return Response(
        img,
        mimetype="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Image-Timestamp": str(ts),
        },
    )


@app.route("/gallery")
def gallery():
    with _lock:
        images = []
        latest = None
        for (cam, obj), (img, ts) in _latest_images.items():
            images.append(
                {
                    "cam": cam,
                    "obj": obj,
                    "ts": int(ts),
                }
            )
            if latest is None or ts > latest["ts"]:
                latest = {"cam": cam, "obj": obj, "ts": int(ts)}
    return jsonify({"images": images, "topic": MQTT_TOPIC, "latest": latest})


@app.route("/status")
def status():
    with _lock:
        count = len(_latest_images)
        cams = sorted(set(cam for (cam, obj) in _latest_images))
        objects = sorted(set(obj for (cam, obj) in _latest_images))
    return jsonify(
        {
            "topic": MQTT_TOPIC,
            "num_images": count,
            "cameras": cams,
            "objects": objects,
            "mqtt_broker": f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}",
        }
    )


@app.route("/events")
def sse_events():
    def gen():
        q = queue.Queue()
        with _sse_clients_lock:
            _sse_clients.append(q)
        try:
            # Send an initial event so the client can update immediately
            yield "data: update\n\n"
            while True:
                # Block until a new event is available
                q.get()
                yield "data: update\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_clients_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(stream_with_context(gen()), mimetype="text/event-stream")


def notify_sse_clients():
    with _sse_clients_lock:
        for q in list(_sse_clients):
            try:
                q.put_nowait(True)
            except Exception:
                pass


def main():
    # Print startup info
    logger.info("Starting mqtt image server")
    logger.info("MQTT topic subscription string: %s", MQTT_TOPIC)
    # Log the effective log level using the numeric _log_level
    logger.info("Log level: %s", logging.getLevelName(_log_level))

    # Start MQTT client (will subscribe in on_connect)
    client = start_mqtt_client()
    try:
        logger.info("Starting Flask HTTP server on %s:%d", HTTP_HOST, HTTP_PORT)
        # Flask's built-in server is fine for small local use. Use gunicorn/uvicorn for production.
        app.run(host=HTTP_HOST, port=HTTP_PORT, threaded=True)
    except Exception as e:
        logger.exception("Unhandled exception in web server: %s", e)
        raise
    finally:
        logger.info("Stopping MQTT client")
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
