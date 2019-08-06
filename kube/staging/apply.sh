#!/usr/bin/env bash

VERSION=$(sentry-cli releases propose-version)

sed -e "s/(version)/$VERSION/g" < django.yaml | kubectl apply -f -
kubectl apply -f nginx.yaml
kubectl apply -f rasa.yaml
kubectl apply -f duckling.yaml