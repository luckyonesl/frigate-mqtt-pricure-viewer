#!/bin/bash



kubectl get secret mosquitto-client-cert  -o jsonpath='{.data.tls\.key}'|base64 -D > client.key
kubectl get secret mosquitto-client-cert  -o jsonpath='{.data.tls\.crt}'|base64 -D > client.crt
kubectl get secret mosquitto-client-cert  -o jsonpath='{.data.ca\.crt}'|base64 -D > signingca.crt

cat signingca.crt rootca.pem > ca-chain.pem

openssl s_client -connect mosquitto.k3s1.lan:443 -CAfile ca-cain.pem -cert client.crt -key client.key
