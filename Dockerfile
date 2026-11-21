FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app
COPY local_simulator.html web_server.py ./
COPY vendor/qrcode.min.js ./vendor/qrcode.min.js
COPY vendor/LICENSE-qrcodejs ./vendor/LICENSE-qrcodejs

USER 10001:10001
EXPOSE 8080
CMD ["python", "web_server.py"]
