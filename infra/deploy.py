import os
import json
import time
import base64
import boto3
from botocore.exceptions import ClientError

REGION = "us-east-2"
AMI_ID = "ami-0d31a22b09ceec4db"  # Amazon Linux 2023 en us-east-2
INSTANCE_TYPE = "t3.micro"
KEY_NAME = "ServidorFTP"
SG_NAME = "CloudVault-Web-SG"
TABLE_NAME = "CloudVault_Archivos"
STATE_FILE = os.path.expanduser("~/proyecto-final-aws/infra/estado_infra.json")
APP_FILE = os.path.expanduser("~/proyecto-final-aws/app/app.py")

def get_active_credentials():
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()
    return creds.access_key, creds.secret_key, creds.token

def deploy_all():
    print("====================================================")
    print("  DESPLIEGUE AUTOMATIZADO DE INFRAESTRUCTURA AWS")
    print("====================================================\n")

    sts = boto3.client("sts", region_name=REGION)
    account_id = sts.get_caller_identity()["Account"]
    bucket_name = f"cloudvault-storage-{account_id}-{REGION}"

    ec2 = boto3.client("ec2", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    dynamodb = boto3.client("dynamodb", region_name=REGION)

    # 1. Crear Bucket S3
    print(f"[1/4] Configurando Bucket S3: {bucket_name}...")
    try:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": REGION}
        )
        print("      -> Bucket S3 creado exitosamente.")
    except ClientError as e:
        if e.response["Error"]["Code"] in ["BucketAlreadyOwnedByYou", "BucketAlreadyExists"]:
            print("      -> El Bucket S3 ya existia, reutilizando.")
        else:
            raise

    # 2. Crear Tabla DynamoDB
    print(f"[2/4] Configurando Tabla DynamoDB: {TABLE_NAME}...")
    try:
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "file_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "file_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST"
        )
        waiter_db = dynamodb.get_waiter("table_exists")
        waiter_db.wait(TableName=TABLE_NAME)
        print("      -> Tabla DynamoDB activa.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print("      -> La tabla DynamoDB ya existia, reutilizando.")
        else:
            raise

    # 3. Crear Security Group (Puertos 80 HTTP y 22 SSH)
    print(f"[3/4] Configurando Security Group: {SG_NAME}...")
    try:
        sg_resp = ec2.create_security_group(
            GroupName=SG_NAME,
            Description="Permite trafico HTTP (80) y SSH (22) para CloudVault"
        )
        sg_id = sg_resp["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}
            ]
        )
        print(f"      -> Security Group creado: {sg_id}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidGroup.Duplicate":
            sgs = ec2.describe_security_groups(GroupNames=[SG_NAME])
            sg_id = sgs["SecurityGroups"][0]["GroupId"]
            print(f"      -> Security Group ya existia, reutilizando: {sg_id}")
        else:
            raise

    # 4. Preparar User Data con la App Web y credenciales de sesion
    print("[4/4] Lanzando servidor web EC2 y desplegando aplicacion...")
    access_key, secret_key, session_token = get_active_credentials()
    with open(APP_FILE, "r", encoding="utf-8") as f:
        app_code_b64 = base64.b64encode(f.read().encode("utf-8")).decode("utf-8")

    user_data_script = f"""#!/bin/bash
dnf update -y
dnf install -y python3-pip
pip3 install flask boto3

mkdir -p /opt/cloudvault
echo "{app_code_b64}" | base64 -d > /opt/cloudvault/app.py

cat << 'ENVEOF' > /opt/cloudvault/.env
AWS_REGION={REGION}
S3_BUCKET_NAME={bucket_name}
DYNAMO_TABLE_NAME={TABLE_NAME}
AWS_ACCESS_KEY_ID={access_key}
AWS_SECRET_ACCESS_KEY={secret_key}
AWS_SESSION_TOKEN={session_token or ""}
ENVEOF

cat << 'SVCEOF' > /etc/systemd/system/cloudvault.service
[Unit]
Description=CloudVault Web App
After=network.target

[Service]
EnvironmentFile=/opt/cloudvault/.env
ExecStart=/usr/bin/python3 /opt/cloudvault/app.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable cloudvault
systemctl start cloudvault
"""

    instance_resp = ec2.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        SecurityGroupIds=[sg_id],
        MinCount=1,
        MaxCount=1,
        UserData=user_data_script,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "CloudVault-WebServer"}]
        }]
    )

    instance_id = instance_resp["Instances"][0]["InstanceId"]
    print(f"      -> Instancia iniciada ({instance_id}). Esperando estado RUNNING...")
    waiter_ec2 = ec2.get_waiter("instance_running")
    waiter_ec2.wait(InstanceIds=[instance_id])

    desc = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = desc["Reservations"][0]["Instances"][0]["PublicIpAddress"]

    # Guardar estado para scripts de resiliencia y limpieza
    state = {
        "region": REGION,
        "bucket_name": bucket_name,
        "table_name": TABLE_NAME,
        "sg_id": sg_id,
        "instance_id": instance_id,
        "public_ip": public_ip
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

    print("\n====================================================")
    print("  ¡DESPLIEGUE COMPLETADO CON EXITO!")
    print(f"  Instance ID : {instance_id}")
    print(f"  URL Web     : http://{public_ip}")
    print("  Nota: Espera ~45 segundos mientras EC2 termina de")
    print("        instalar Flask y abre la URL en tu navegador.")
    print("====================================================\n")

if __name__ == "__main__":
    deploy_all()
