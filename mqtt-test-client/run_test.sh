#!/bin/bash
TESTHOST=${TESTHOST:-mosquitto}
TESTPORT=${TESTPORT:-8883}
sleep 2
echo "test ssl"
openssl s_client -connect "${TESTHOST}:${TESTPORT}" -CAfile /etc/ssl/certs/ca.pem
echo "return $?"

echo "test cert auth"
openssl s_client -connect "${TESTHOST}:${TESTPORT}" -cert /etc/ssl/certs/client.crt -key /etc/ssl/private/client.key -CAfile /etc/ssl/certs/ca.pem
echo "return $?"
sleep 2

echo "test mqtt publish insecure"
mosquitto_pub -d -i mqtt-tester --insecure -h ${TESTHOST} -p ${TESTPORT} --cafile /etc/ssl/certs/ca.pem --cert /etc/ssl/certs/client.crt --key /etc/ssl/private/client.key -t frigate/test -m 'Hello MQTT'
echo "return $?"
echo "test mqtt publish with hostname ${TESTHOST}"
mosquitto_pub -d -i mqtt-tester -h ${TESTHOST} -p ${TESTPORT} --cafile /etc/ssl/certs/ca.pem --cert /etc/ssl/certs/client.crt --key /etc/ssl/private/client.key -t frigate/test -m 'Hello MQTT secure'
echo "return $?"

echo "sleeping...."
sleep 9000
