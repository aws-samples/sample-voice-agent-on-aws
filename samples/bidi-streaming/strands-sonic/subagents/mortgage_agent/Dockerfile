FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY main.py ./

ENV HOST="0.0.0.0"
ENV PORT=9000

EXPOSE 9000

CMD ["python", "main.py"]
