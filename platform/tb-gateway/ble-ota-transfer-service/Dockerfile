# Usa una imagen base de Python
FROM python:3-alpine

# Copia el archivo de requisitos y el script al contenedor
COPY requirements.txt /app/requirements.txt
COPY ble_ota_transfer_api.py /app/ble_ota_transfer_api.py

# Establece el directorio de trabajo
WORKDIR /app

# Instala las dependencias
RUN pip install -r requirements.txt

# Ejecuta el script
CMD ["uvicorn", "ble_ota_transfer_api:app", "--host", "0.0.0.0", "--port", "5000" ]
