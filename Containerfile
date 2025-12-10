FROM python:3.12-alpine AS builder

WORKDIR /build

RUN pip install --no-cache-dir --root-user-action=ignore uv

COPY setup.cfg setup.py LICENSE README.md ./
COPY preoccupied/ ./preoccupied/
RUN uv build .


FROM python:3.12-alpine

WORKDIR /setup

RUN apk update && apk add git

COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY --from=builder /build/dist/preoccupied_gitsync-*.whl .
RUN pip install --no-cache-dir --root-user-action=ignore --no-deps preoccupied_gitsync-*.whl

WORKDIR /app
RUN rm -rf /setup

CMD ["uvicorn", "preoccupied.gitsync:app", "--host", "0.0.0.0", "--port", "8080"]


# The end.
