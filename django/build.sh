#!/usr/bin/env bash

VERSION=$(sentry-cli releases propose-version)

cd react/operator_interface || exit
yarn build
cd ../..

cd react/payments_form || exit
yarn webpack --confif webpack.prod.js
cd ../..

docker build -t "theenbyperor/wewillfixyourpcbot_django:$VERSION" .
docker push "theenbyperor/wewillfixyourpcbot_django:$VERSION"