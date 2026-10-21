FROM python:3.12-slim
RUN pip install --no-cache-dir pynetgear==0.10.10 prometheus-client==0.21.1
COPY exporter.py /exporter.py
USER nobody
EXPOSE 9100
CMD ["python", "-u", "/exporter.py"]
