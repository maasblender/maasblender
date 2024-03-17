FROM eclipse-temurin:17
USER root
RUN apt-get -y update \
 && apt-get install -y python3-pip wget \
 && mkdir /root/otp \
 && wget "https://repo1.maven.org/maven2/org/opentripplanner/otp/2.4.0/otp-2.4.0-shaded.jar" -O /root/otp/otp-shaded.jar

WORKDIR /home
COPY requirements.txt ./
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip \
 && pip install --upgrade setuptools \
 && pip install -r requirements.txt

COPY . .

ENTRYPOINT ["uvicorn", "controller:app"]
CMD ["--host", "0.0.0.0", "--port", "80"]