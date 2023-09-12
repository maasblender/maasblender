FROM python:3.10-slim
USER root
RUN apt-get -y update

WORKDIR /home
COPY requirements.txt ./
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip \
 && pip install --upgrade setuptools \
 && pip install -r requirements.txt

COPY . .

ENTRYPOINT ["uvicorn", "controller:app"]
CMD ["--host", "0.0.0.0", "--port", "80"]
