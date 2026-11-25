import os
import uuid
import urllib.request
from datetime import datetime
import boto3
from flask import Flask, request, redirect, url_for, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.urandom(24)

REGION = os.environ.get("AWS_REGION", "us-east-2")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
TABLE_NAME = os.environ.get("DYNAMO_TABLE_NAME", "CloudVault_Archivos")

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudVault AWS - Gestor Documental Resiliente</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
    <nav class="bg-slate-800 border-b border-slate-700 px-6 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-3">
            <span class="text-2xl">☁️</span>
            <h1 class="text-xl font-bold text-sky-400">CloudVault <span class="text-xs bg-sky-900 text-sky-300 px-2 py-1 rounded ml-2">AWS EC2 + S3 + DynamoDB</span></h1>
        </div>
        <div class="text-xs text-slate-400">
            Servidor ID: <span class="font-mono text-emerald-400">{{ instance_id }}</span>
        </div>
    </nav>

    <main class="max-w-5xl mx-auto p-6">
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="bg-emerald-900/60 border border-emerald-500 text-emerald-200 px-4 py-3 rounded mb-6">
              {{ messages[0] }}
            </div>
          {% endif %}
        {% endwith %}

        <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg mb-8">
            <h2 class="text-lg font-semibold mb-4 text-white">Subir nuevo documento a la nube</h2>
            <form action="/upload" method="post" enctype="multipart/form-data" class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                <div>
                    <label class="block text-sm text-slate-400 mb-1">Archivo</label>
                    <input type="file" name="file" required class="w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-sky-600 file:text-white hover:file:bg-sky-500 cursor-pointer">
                </div>
                <div>
                    <label class="block text-sm text-slate-400 mb-1">Descripción / Etiqueta</label>
                    <input type="text" name="description" placeholder="Ej. Evidencia Proyecto Final" required class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500">
                </div>
                <div>
                    <button type="submit" class="w-full bg-sky-600 hover:bg-sky-500 text-white font-semibold py-2 px-4 rounded-lg transition">
                        ⬆️ Subir a S3 & DynamoDB
                    </button>
                </div>
            </form>
        </div>

        <div class="bg-slate-800 rounded-xl border border-slate-700 shadow-lg overflow-hidden">
            <div class="px-6 py-4 border-b border-slate-700 flex justify-between items-center">
                <h2 class="text-lg font-semibold">Archivos Almacenados ({{ files|length }})</h2>
                <span class="text-xs text-slate-400">Bucket: {{ bucket }}</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-900/50 text-slate-400 text-xs uppercase">
                            <th class="py-3 px-6">Nombre de Archivo</th>
                            <th class="py-3 px-6">Descripción</th>
                            <th class="py-3 px-6">Tamaño</th>
                            <th class="py-3 px-6">Fecha UTC</th>
                            <th class="py-3 px-6 text-right">Acciones</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-700 text-sm">
                        {% for f in files %}
                        <tr class="hover:bg-slate-700/40">
                            <td class="py-3 px-6 font-medium text-sky-300">{{ f.filename }}</td>
                            <td class="py-3 px-6 text-slate-300">{{ f.description }}</td>
                            <td class="py-3 px-6 text-slate-400">{{ f.size_kb }} KB</td>
                            <td class="py-3 px-6 text-slate-400 font-mono text-xs">{{ f.uploaded_at }}</td>
                            <td class="py-3 px-6 text-right space-x-2">
                                <a href="/download/{{ f.file_id }}" class="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1 rounded text-xs">Descargar</a>
                                <a href="/delete/{{ f.file_id }}" class="bg-rose-600 hover:bg-rose-500 text-white px-3 py-1 rounded text-xs">Eliminar</a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" class="py-8 text-center text-slate-500">No hay archivos almacenados todavía. ¡Sube el primero arriba!</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </main>
</body>
</html>
"""

def get_instance_id():
    try:
        token_req = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT", headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"})
        token = urllib.request.urlopen(token_req, timeout=1).read().decode()
        req = urllib.request.Request("http://169.254.169.254/latest/meta-data/instance-id", headers={"X-aws-ec2-metadata-token": token})
        return urllib.request.urlopen(req, timeout=1).read().decode()
    except Exception:
        return "EC2-Instance"

@app.route("/")
def index():
    response = table.scan()
    items = sorted(response.get("Items", []), key=lambda x: x.get("uploaded_at", ""), reverse=True)
    return render_template_string(HTML_TEMPLATE, files=items, bucket=BUCKET_NAME, instance_id=get_instance_id())

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    description = request.form.get("description", "Sin descripción")
    if not file or file.filename == "":
        return redirect(url_for("index"))

    file_id = str(uuid.uuid4())[:8]
    s3_key = f"{file_id}_{file.filename}"
    file_bytes = file.read()
    size_kb = round(len(file_bytes) / 1024, 2)

    s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=file_bytes)
    table.put_item(Item={
        "file_id": file_id,
        "filename": file.filename,
        "s3_key": s3_key,
        "description": description,
        "size_kb": str(size_kb),
        "uploaded_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    })

    flash(f"Archivo '{file.filename}' guardado en S3 y registrado en DynamoDB.")
    return redirect(url_for("index"))

@app.route("/download/<file_id>")
def download(file_id):
    resp = table.get_item(Key={"file_id": file_id})
    item = resp.get("Item")
    if not item:
        return "Archivo no encontrado", 404
    url = s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET_NAME, "Key": item["s3_key"]}, ExpiresIn=300)
    return redirect(url)

@app.route("/delete/<file_id>")
def delete(file_id):
    resp = table.get_item(Key={"file_id": file_id})
    item = resp.get("Item")
    if item:
        s3.delete_object(Bucket=BUCKET_NAME, Key=item["s3_key"])
        table.delete_item(Key={"file_id": file_id})
        flash(f"Archivo '{item['filename']}' eliminado de S3 y DynamoDB.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
