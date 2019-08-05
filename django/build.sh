#!/usr/bin/env bash

cd react/operator_interface || exit
yarn build
cd ../..

cd react/payments_form || exit
yarn webpack --conf webpack.prod.js
cd ../..