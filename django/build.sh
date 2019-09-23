#!/usr/bin/env bash

PAYMENT_PROVIDER="WORLDPAY";
export PAYMENT_PROVIDER

VERSION=$(sentry-cli releases propose-version || exit)

cd react/operator_interface || exit
yarn build || exit
cd ../..

cd react/payments_form || exit
yarn webpack --config webpack.prod.js || exit
cd ../..

docker build -t "theenbyperor/wewillfixyourpcbot_django:$VERSION" . || exit
docker push "theenbyperor/wewillfixyourpcbot_django:$VERSION" || exit

sentry-cli releases --org we-will-fix-your-pc new -p bot-server $VERSION || exit
sentry-cli releases --org we-will-fix-your-pc set-commits --auto $VERSION