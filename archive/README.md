sed -i 's/127.0.0.1/192.168.31.116/g' ~/.kube/config-k3s

scp user@192.168.31.116:/etc/rancher/k3s/k3s.yaml ~/.kube/config

ssh kamronbek@192.168.31.116 "sudo cat /etc/rancher/k3s/k3s.yaml" > ~/.kube/config
