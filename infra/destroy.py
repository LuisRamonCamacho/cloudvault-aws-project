import os
import json
import boto3

STATE_FILE = os.path.expanduser("~/proyecto-final-aws/infra/estado_infra.json")

def destroy_all():
    if not os.path.exists(STATE_FILE):
        print("No se encontro archivo de estado. Nada que eliminar.")
        return

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    region = state["region"]
    ec2 = boto3.client("ec2", region_name=region)
    s3 = boto3.resource("s3", region_name=region)
    dynamodb = boto3.client("dynamodb", region_name=region)

    print("====================================================")
    print("  ELIMINANDO TODA LA INFRAESTRUCTURA DE AWS")
    print("====================================================")

    # 1. Terminar EC2
    inst_id = state["instance_id"]
    print(f"[1/4] Terminando instancia EC2 {inst_id}...")
    ec2.terminate_instances(InstanceIds=[inst_id])
    ec2.get_waiter("instance_terminated").wait(InstanceIds=[inst_id])
    print("      -> Instancia terminada.")

    # 2. Vaciar y eliminar S3
    bucket_name = state["bucket_name"]
    print(f"[2/4] Vaciando y eliminando Bucket S3 {bucket_name}...")
    bucket = s3.Bucket(bucket_name)
    bucket.objects.all().delete()
    bucket.delete()
    print("      -> Bucket S3 eliminado.")

    # 3. Eliminar DynamoDB
    table_name = state["table_name"]
    print(f"[3/4] Eliminando tabla DynamoDB {table_name}...")
    dynamodb.delete_table(TableName=table_name)
    print("      -> Tabla DynamoDB eliminada.")

    # 4. Eliminar Security Group
    sg_id = state["sg_id"]
    print(f"[4/4] Eliminando Security Group {sg_id}...")
    ec2.delete_security_group(GroupId=sg_id)
    print("      -> Security Group eliminado.")

    os.remove(STATE_FILE)
    print("\n¡Limpieza total completada!")

if __name__ == "__main__":
    destroy_all()
