#!/bin/bash
set -e
WKDIR=$(dirname `readlink -f $0`)
DOCKER_COMPOSE_CMD=${DOCKER_COMPOSE_CMD:-docker compose}
export COMPOSE_FILE=${WKDIR}/docker-compose-noauto.yml
echo "START generating needed secrets for testing"

export CERTDIR=${WKDIR}/../secrets/certs

if [ ! -d "${CERTDIR}" ];then
	mkdir -p "${CERTDIR}"
fi

echo "CERT MATERIAL SOURCE DIR -> $CERTDIR"
if [ ! -f "${CERTDIR}/ca-key.pem" ];then
   ${DOCKER_COMPOSE_CMD} up -d
fi

#generate a client cert named admin
if [ ! -f "${CERTDIR}/admin-key.pem" ];then
   echo "generating cert with CN=admin as client cert"
   ${DOCKER_COMPOSE_CMD} run \
     -e SSL_SUBJECT=admin \
     -e SSL_KEY=admin-key.pem \
     -e SSL_CERT=admin-cert.pem \
     --rm ssl-ca > /dev/null
fi

if [ ! -f "${CERTDIR}/mqtt.example.com-key.pem" ];then
   echo "generating cert for server mqtt.example.com"
   ${DOCKER_COMPOSE_CMD} run \
     -e SSL_SUBJECT=mqtt.example.com \
     -e SSL_DNS=mqtt.example.com \
     -e SSL_KEY=mqtt.example.com-key.pem \
     -e SSL_CERT=mqtt.example.com-cert.pem \
     --rm ssl-ca > /dev/null
fi

echo "FINISH generating needed secrets for testing"
