FROM python:3.7

RUN mkdir app
RUN useradd app
WORKDIR /app
RUN curl -sL https://deb.nodesource.com/setup_10.x | bash - && apt-get install -y nodejs
RUN curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - && \
  echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list && \
  apt-get update && apt-get install yarn
RUN pip install -U pip

COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY django-keycloak-auth-1.0.any-any.tar.gz /
RUN pip install /django-keycloak-auth-1.0.any-any.tar.gz && rm /django-keycloak-auth-1.0.any-any.tar.gz

USER app:app

COPY . /app