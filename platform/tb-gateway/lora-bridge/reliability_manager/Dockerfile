# Usa una imagen base de Python
FROM python:3-alpine

# Copia el archivo de requisitos y el script al contenedor
COPY requirements.txt /app/requirements.txt
COPY reliability_manager.py /app/reliability_manager.py

# Establece el directorio de trabajo
WORKDIR /app

# Instala las dependencias
RUN pip install -r requirements.txt

# Varianles de entorno
ENV mqtt_user=
ENV mqtt_password=
ENV device_id_list=

# Ejecuta el script
CMD ["python", "reliability_manager.py" ]
