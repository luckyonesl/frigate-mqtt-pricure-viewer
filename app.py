#!/usr/bin/env python3
"""
Simple Flask app that subscribes to an MQTT topic and serves
the last JPEG message received on that topic.

Environment variables:
- MQTT_BROKER_HOST (default: localhost)
- MQTT_BROKER_PORT (default: 1883)
- MQTT_USERNAME (optional)
- MQTT_PASSWORD (optional)
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

from flask import Flask, Response, render_template_string, jsonify
import paho.mqtt.client as mqtt

# Configuration from env
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)
# Default to the snapshot topic which contains raw JPEG payloads.
# Can be overridden with the MQTT_TOPIC environment variable.
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "frigate/hofcam1/person/snapshot")

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
_last_image = None  # bytes of JPEG
_last_image_ts = 0.0  # epoch seconds
_lock = threading.RLock()


def store_image_if_jpeg(candidate_bytes: bytes) -> bool:
    """
    If candidate_bytes contains a jpeg (raw or base64-encoded), store it and return True.
    Otherwise return False.
    """
    global _last_image, _last_image_ts
    if not candidate_bytes:
        return False

    # If the payload already looks like JPEG bytes:
    if candidate_bytes[:3] == b"\xff\xd8\xff":
        with _lock:
            _last_image = candidate_bytes
            _last_image_ts = time.time()
        logger.info("Stored raw JPEG image (size=%d)", len(candidate_bytes))
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
                _last_image = decoded
                _last_image_ts = time.time()
            logger.info("Stored base64-decoded JPEG image (size=%d)", len(decoded))
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
    # Accept messages that match the configured subscription. This supports
    # wildcards (e.g. '+' and '#') when the MQTT_TOPIC env var contains them.
    try:
        matches = mqtt.topic_matches_sub(MQTT_TOPIC, msg.topic)
    except Exception:
        # Fallback to exact match if topic matching utility isn't available for any reason
        matches = msg.topic == MQTT_TOPIC

    if matches:
        ok = store_image_if_jpeg(msg.payload)
        if not ok:
            logger.warning(
                "Received message on %s but it is not a recognizable JPEG", msg.topic
            )


def start_mqtt_client():
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
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
    # Simple page that displays the latest image and auto-refreshes it via JS
    html = """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8"/>
        <title>Latest MQTT Image - {{topic}}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 1rem; }
          .meta { margin-top: 0.5rem; color: #666; }
          img { max-width: 100%; height: auto; border: 1px solid #ccc; }
        </style>
      </head>
      <body>
        <h1>Latest MQTT Image</h1>
        <div>
          <img id="lastImg" src="/image.jpg?ts={{ts}}" alt="No image yet" />
        </div>
        <div class="meta">
          Topic: <code>{{topic}}</code> • Last updated: <span id="lastUpdated">{{human_ts}}</span>
        </div>
        <script>
          // simple periodic reload by changing a cache-busting query string
          const ms = {{refresh_ms}};
          setInterval(() => {
            const img = document.getElementById('lastImg');
            const now = Date.now();
            img.src = '/image.jpg?ts=' + now;
            document.getElementById('lastUpdated').innerText = new Date().toLocaleString();
          }, ms);
        </script>
      </body>
    </html>
    """
    with _lock:
        ts = int(_last_image_ts) if _last_image_ts else 0
    human_ts = time.ctime(_last_image_ts) if _last_image_ts else "never"
    return render_template_string(
        html, topic=MQTT_TOPIC, ts=ts, human_ts=human_ts, refresh_ms=IMAGE_REFRESH_MS
    )


@app.route("/image.jpg")
def image():
    with _lock:
        img = _last_image
        ts = _last_image_ts
    if not img:
        # Simple 204 No Content when no image yet, alternatively return a placeholder.
        return Response(status=204)
    return Response(
        img,
        mimetype="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Image-Timestamp": str(ts),
        },
    )


@app.route("/status")
def status():
    with _lock:
        has = bool(_last_image)
        ts = _last_image_ts
        size = len(_last_image) if _last_image else 0
    return jsonify(
        {
            "topic": MQTT_TOPIC,
            "has_image": has,
            "last_image_ts": ts,
            "last_image_size": size,
            "mqtt_broker": f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}",
        }
    )


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
