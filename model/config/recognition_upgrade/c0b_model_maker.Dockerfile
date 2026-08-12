FROM python:3.10-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY c0b_model_maker_requirements.txt /tmp/c0b_model_maker_requirements.txt

RUN python -m pip install --upgrade pip wheel "setuptools==80.9.0" \
    && python -m pip install -r /tmp/c0b_model_maker_requirements.txt

WORKDIR /workspace

CMD ["python", "-m", "pipeline.tracking.e2e_c0b", "toolchain-preflight", "--output", "artifacts/recognition_upgrade/e2e_c0/c0b_toolchain_docker_preflight_01"]
