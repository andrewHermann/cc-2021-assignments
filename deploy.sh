#!/usr/bin/env bash

set -ex

docker push ajhermann/infoservice:latest || echo "Please make sure you have the image locally and you're logged into docker hub using docker login"

kubectl create -f all.yaml || kubectl rollout restart deployment/infoservice-deployment
