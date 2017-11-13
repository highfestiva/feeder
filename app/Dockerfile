FROM python:3.6

RUN pip install --upgrade pip
RUN pip install flask websockets
ADD hoarder.py /usr/local/
ADD templates/ /usr/local/templates/
ADD static/ /usr/local/static/
WORKDIR /usr/local
CMD ["python3.6", "hoarder.py"]
