#!/usr/bin/env bash

PAYMENT_PROVIDER="WORLDPAY";
export PAYMENT_PROVIDER

VERSION=$(sentry-cli releases propose-version || exit)

cd react/operator_interface || exit
yarn build || exit
cd ../..

cp ../django-keycloak-auth/dist/django-keycloak-auth-1.0.any-any.tar.gz .

docker build -t "theenbyperor/wewillfixyourpcbot_django:$VERSION" . || exit
docker push "theenbyperor/wewillfixyourpcbot_django:$VERSION" || exit

sentry-cli releases --org we-will-fix-your-pc new -p bot-server $VERSION || exit
sentry-cli releases --org we-will-fix-your-pc set-commits --auto $VERSION