import os
import json
import time
import boto3
from deploy import deploy_all

STATE_FILE = os.path.expanduser("~/proyecto-final-aws/infra/estado_infra.json")

def run_resilience_test():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    region = state["region"]
    old_instance = state["instance_id"]
    bucket_name = state["bucket_name"]
    table_name = state["table_name"]

    ec2 = boto3.client("ec2", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    dynamodb = boto3.client("dynamodb", region_name=region)

    print("====================================================")
    print("  PRUEBA DE RESILIENCIA Y AUTO-RECUPERACION")
    print("====================================================")
    print(f"[1] Simulando FALLO CATASTROFICO: Terminando instancia {old_instance}...")
    ec2.terminate_instances(InstanceIds=[old_instance])
    waiter = ec2.get_waiter("instance_terminated")
    waiter.wait(InstanceIds=[old_instance])
    print("    -> Servidor caido/eliminado confirmado.")

    print("\n[2] Verificando integridad de datos desacoplados...")
    objs = s3.list_objects_v2(Bucket=bucket_name).get("Contents", [])
    db_count = dynamodb.scan(TableName=table_name, Select="COUNT")["Count"]
    print(f"    -> Archivos intactos en S3: {len(objs)}")
    print(f"    -> Registros intactos en DynamoDB: {db_count}")

    print("\n[3] Ejecutando recuperacion automatica de la capa de computo...")
    deploy_all()

if __name__ == "__main__":
    run_resilience_test()
