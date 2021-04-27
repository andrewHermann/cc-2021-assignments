FROM debian
RUN apt update && apt -f -y install python3 python3-pip
ADD . /python/
WORKDIR /python
RUN pip3 install -r requirements.txt
CMD ["server.py"]
ENTRYPOINT ["python3"]
EXPOSE 1080