#!/usr/bin/env bash

PAYMENT_PROVIDER="WORLDPAY";
export PAYMENT_PROVIDER

VERSION=$(sentry-cli releases propose-version)

cd react/operator_interface || exit
yarn build
cd ../..

cd react/payments_form || exit
yarn webpack --config webpack.prod.js
cd ../..

docker build -t "theenbyperor/wewillfixyourpcbot_django:$VERSION" .
docker push "theenbyperor/wewillfixyourpcbot_django:$VERSION"

sentry-cli releases --org we-will-fix-your-pc new -p bot-server $VERSION
sentry-cli releases --org we-will-fix-your-pc set-commits --auto $VERSION