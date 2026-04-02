FROM python:3.10-slim

WORKDIR /app

COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt

COPY . .
RUN pip install --no-cache-dir -e .

# Smoke test: validate physics suite
RUN python -m aethermor.validation.validate_all

CMD ["python", "-m", "aethermor.validation.validate_all"]
