helm upgrade --install mosquitto ./mosquitto --namespace mosquitto --create-namespace -f mosquitto/values.yaml
helm uninstall mosquitto  --namespace mosquitto 

