#!/usr/bin/env bash

python3.7 manage.py migrate
python3.7 manage.py collectstatic --noinput

exec "$@"