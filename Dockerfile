# set base image (host OS)
FROM python:3.9

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . /globant

WORKDIR /globant

CMD ["python", "app.py"]