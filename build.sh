#!/usr/bin/env bash

set -ex
## building info service
cd info/
docker build -t infoservice:local .

## tagging info service
docker tag infoservice:local ajhermann/infoservice:latest
