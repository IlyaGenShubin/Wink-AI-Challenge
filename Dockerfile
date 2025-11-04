FROM python:3.11-slim

# Системные зависимости для weasyprint (PDF), pdfminer и шрифтов
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    pango1.0-tools \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    libxml2 \
    libxslt1.1 \
    fonts-dejavu \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Локаль для русского
RUN sed -i 's/# ru_RU.UTF-8/ru_RU.UTF-8/' /etc/locale.gen && locale-gen
ENV LANG=ru_RU.UTF-8
ENV LC_ALL=ru_RU.UTF-8

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники и конфиги
COPY app /app/app
COPY config /app/config

# Директории данных
RUN mkdir -p /app/data/uploads /app/data/analyses /app/data/reports /app/data/cache

EXPOSE 8000

# По умолчанию команда задаётся в docker-compose
