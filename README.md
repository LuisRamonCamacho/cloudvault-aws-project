# CloudVault AWS — Gestor Documental Resiliente (IaC)

Aplicación web desplegada automáticamente en AWS utilizando **Amazon EC2**, **Amazon S3** y **Amazon DynamoDB**, orquestada mediante scripts en Python (`boto3`) bajo principios de Infraestructura como Código (IaC).

## Estructura del Repositorio

* `app/app.py`: Aplicación web (Backend Flask + Frontend TailwindCSS) para carga, listado, descarga mediante URLs prefirmadas y eliminación de documentos.
* `infra/deploy.py`: Script maestro de aprovisionamiento automático (crea Bucket S3, Tabla DynamoDB, Security Group e instancia EC2 con *User Data*).
* `infra/resilience_test.py`: Script de pruebas de resiliencia que simula el fallo catastrófico de la instancia EC2, verifica la integridad de los datos en S3/DynamoDB y auto-recupera el servidor.
* `infra/destroy.py`: Script de limpieza completa de todos los recursos aprovisionados.

## Despliegue Rápido

```bash
python3 infra/deploy.py
