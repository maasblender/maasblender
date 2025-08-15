FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    openjdk-21-jre \
    wget \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /var/otp \
    && wget "https://repo1.maven.org/maven2/org/opentripplanner/otp/2.4.0/otp-2.4.0-shaded.jar" -O /var/otp/otp-shaded.jar

COPY requirements.txt ./
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip \
    && pip install --upgrade setuptools \
    && pip install -r requirements.txt

RUN chown nobody -R /var/otp

USER nobody

WORKDIR /app
COPY . .

ENTRYPOINT ["uvicorn", "controller:app"]
CMD ["--host", "0.0.0.0", "--port", "80"]