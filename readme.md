# mqtt jpeg display server

## Project Purpose

This project provides a lightweight web server that displays JPEG images received via MQTT topics, typically snapshots from security or monitoring systems like Frigate. It is intended for use cases where you want a simple, browser-accessible view of the latest images published to MQTT, such as for dashboards, wall displays, or quick monitoring without a full NVR interface.

## About Frigate

[Frigate](https://frigate.video/) is an open-source Network Video Recorder (NVR) with real-time AI object detection. It publishes events, snapshots, and alerts via MQTT topics, making it easy to integrate with other systems. This project is designed to display JPEG images (such as snapshots) published by Frigate to MQTT topics.

## Environment Variables Reference (`run.sh`)

The `run.sh` script configures and launches the server. You can override any variable by setting it in your environment before running the script.

| Variable           | Default                        | Description                                                                 |
|--------------------|--------------------------------|-----------------------------------------------------------------------------|
| `MQTT_BROKER_HOST` | `localhost`                    | Hostname or IP address of the MQTT broker                                   |
| `MQTT_BROKER_PORT` | `1883`                         | Port for the MQTT broker                                                    |
| `MQTT_USERNAME`    | *(empty)*                      | Username for MQTT authentication (optional)                                 |
| `MQTT_PASSWORD`    | *(empty)*                      | Password for MQTT authentication (optional)                                 |
| `MQTT_TOPIC`       | `frigate/+/+/snapshot`         | MQTT topic to subscribe to for image snapshots from Frigate                 |
| `HTTP_HOST`        | `0.0.0.0`                      | Host/IP for the HTTP server to bind                                         |
| `HTTP_PORT`        | `8080`                         | Port for the HTTP server                                                    |
| `IMAGE_REFRESH_MS` | `2000`                         | Image refresh interval in milliseconds (client-side polling)                |

**Example usage:**
```sh
MQTT_BROKER_HOST=broker.local MQTT_USERNAME=user ./run.sh
```

The script prints the effective configuration (masking sensitive values) before starting the application.

## TODO

- Build and publish a Docker container for easy deployment
- Add support for mutual SSL (client certificate) authentication for MQTT
- Improve error handling and logging
- Add automated tests
- Provide a sample dashboard or web UI enhancements
- Document advanced configuration options
