FROM python:3.11-slim

ARG jdk_version=21
ARG otp_version=2.6.0
ARG jdk_url=https://download.oracle.com/java/${jdk_version}/latest/jdk-${jdk_version}_linux-x64_bin.deb
ARG otp_url=https://repo1.maven.org/maven2/org/opentripplanner/otp/${otp_version}/otp-${otp_version}-shaded.jar

RUN apt-get update && apt-get install -y \
    wget \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN wget ${jdk_url} \
 && dpkg -i jdk-*_linux-x64_bin.deb \
 && mkdir /var/otp \
 && wget ${otp_url} -O /var/otp/otp-shaded.jar

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