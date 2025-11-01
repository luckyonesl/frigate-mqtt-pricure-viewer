# Mosquitto Helm Chart

This Helm chart deploys the [Eclipse Mosquitto](https://mosquitto.org/) MQTT broker on Kubernetes with **mutual TLS authentication** (client certificate authentication) using [cert-manager](https://cert-manager.io/) for certificate management. The chart is pre-configured to use a cert-manager Issuer or ClusterIssuer (such as `subca-key-pair`) to automatically provision server certificates for Mosquitto.

---

## Features

- Deploys Mosquitto with secure MQTT over TLS (port 8883)
- Enforces client certificate authentication (mutual TLS)
- Integrates with cert-manager for automated certificate issuance and renewal
- Customizable via `values.yaml`

---

## Prerequisites

- Kubernetes cluster
- [Helm](https://helm.sh/) 3.x
- [cert-manager](https://cert-manager.io/) installed and running
- A cert-manager Issuer or ClusterIssuer named `subca-key-pair` (or your chosen name) that issues certificates from your CA

---

## Usage

### 1. Prepare cert-manager Issuer

Ensure you have a `ClusterIssuer` or `Issuer` named `subca-key-pair` that issues certificates from your intermediate CA. Example:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: subca-key-pair
spec:
  ca:
    secretName: subca-key-pair-secret
```

### 2. Install the Chart

```sh
helm install mosquitto ./helm/mosquitto
```

Or to customize values:

```sh
helm install mosquitto ./helm/mosquitto -f my-values.yaml
```

### 3. Configuration

Edit `values.yaml` to set:

- `certManager.issuerName`: Name of your cert-manager Issuer/ClusterIssuer (default: `subca-key-pair`)
- `certManager.issuerKind`: `Issuer` or `ClusterIssuer`
- `certManager.commonName` and `certManager.dnsNames`: The CN and SANs for the Mosquitto server certificate

### 4. Access

- The broker is exposed on port 8883 (MQTTS).
- Clients **must** present a valid client certificate signed by your CA.

---

## Client Certificate Authentication

To connect, clients must have a certificate signed by the same CA as the Mosquitto server. You can use cert-manager to issue client certificates as well.

Example client Certificate resource:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: mqtt-client
spec:
  secretName: mqtt-client-tls
  duration: 2160h
  renewBefore: 360h
  commonName: my-client
  issuerRef:
    name: subca-key-pair
    kind: ClusterIssuer
  usages:
    - client auth
```

---

## Files

- `Chart.yaml` - Helm chart metadata
- `values.yaml` - Default configuration values
- `templates/configmap.yaml` - Mosquitto configuration (enforces mutual TLS)
- `templates/certificate.yaml` - cert-manager Certificate for Mosquitto server
- `templates/deployment.yaml` - Mosquitto Deployment
- `templates/service.yaml` - Service exposing Mosquitto

---

## Uninstall

```sh
helm uninstall mosquitto
```

---

## References

- [Eclipse Mosquitto Documentation](https://mosquitto.org/documentation/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)

---