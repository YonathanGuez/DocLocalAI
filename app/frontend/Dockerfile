FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /opt/app-root/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ui.py .
COPY .streamlit .streamlit

EXPOSE 8501
CMD ["streamlit", "run", "ui.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
