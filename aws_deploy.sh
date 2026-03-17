#!/bin/bash

# Script de deployment a AWS Lambda + EventBridge + S3
# Solución más barata: ~$0.20/mes en Free Tier

set -e

# ===== VARIABLES =====
REGION="us-east-1"  # Free tier region
PROJECT_NAME="betting-analyzer"
FUNCTION_NAME="daily-betting-analysis"
BUCKET_NAME="${PROJECT_NAME}-$(date +%s)"
LAYER_NAME="betting-dependencies"

echo "🚀 Iniciando deployment de la solución más barata..."
echo "📍 Región: $REGION"
echo "💰 Costo estimado: ~$0.20/mes"

# ===== 1. CREAR BUCKET S3 =====
echo ""
echo "📦 Creando bucket S3..."
aws s3 mb "s3://${BUCKET_NAME}" --region "$REGION" || echo "Bucket ya existe"
aws s3api put-bucket-versioning --bucket "$BUCKET_NAME" --versioning-configuration Status=Suspended

# ===== 2. CREAR LAMBDA LAYER CON DEPENDENCIAS =====
echo ""
echo "📚 Empaquetando dependencias (Python 3.11)..."
mkdir -p lambda_build/python/lib/python3.11/site-packages
cd lambda_build

# Instalar dependencias
pip install -r ../requirements.txt -t python/lib/python3.11/site-packages/ --quiet

# Crear ZIP del layer
zip -r -q ../lambda_layer.zip python/
cd ..

echo "✅ Layer creado: lambda_layer.zip"

# ===== 3. CREAR FUNCIÓN LAMBDA =====
echo ""
echo "⚙️  Preparando código Lambda..."
mkdir -p lambda_function
cp -r src lambda_function/
cp .env.example lambda_function/.env || true
cp config.py lambda_function/ || true

cat > lambda_function/lambda_handler.py << 'EOF'
import json
import boto3
import subprocess
import os
from datetime import datetime, date
from pathlib import Path

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def lambda_handler(event, context):
    """
    Handler principal de Lambda
    Ejecuta análisis diario y guarda en S3
    """
    try:
        target_date = event.get('date', str(date.today()))
        
        # Ejecutar análisis
        print(f"📊 Ejecutando análisis para {target_date}...")
        result = subprocess.run([
            'python', '-m', 'src.app', 'today',
            '--date', target_date,
            '--html'
        ], capture_output=True, text=True, cwd='/var/task')
        
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': result.stderr})
            }
        
        print(f"✅ Análisis completado")
        
        # Buscar archivo HTML generado
        home = os.path.expanduser('~')
        html_file = f"{home}/reporte_apuestas_{target_date}.html"
        
        if os.path.exists(html_file):
            # Subir a S3
            with open(html_file, 'rb') as f:
                s3_key = f"reportes/{target_date}.html"
                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=s3_key,
                    Body=f.read(),
                    ContentType='text/html'
                )
            
            # Generar URL pública
            html_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
            
            print(f"📤 Reporte guardado en: {html_url}")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Análisis completado',
                    'date': target_date,
                    'report_url': html_url
                })
            }
        else:
            print(f"⚠️  Archivo HTML no encontrado: {html_file}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Análisis completado sin partidos disponibles',
                    'date': target_date
                })
            }
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

EOF

# Crear ZIP de la función
cd lambda_function
zip -r -q ../lambda_function.zip . -x "*.git*" "__pycache__/*"
cd ..

echo "✅ Función Lambda creada: lambda_function.zip"

# ===== 4. CREAR ROLE IAM =====
echo ""
echo "🔐 Creando rol IAM..."

TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

INLINE_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::'$BUCKET_NAME'/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}'

ROLE_NAME="${PROJECT_NAME}-lambda-role"

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "$TRUST_POLICY" \
  --region "$REGION" 2>/dev/null || echo "Rol ya existe"

echo "$INLINE_POLICY" > /tmp/policy.json
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "${PROJECT_NAME}-s3-policy" \
  --policy-document file:///tmp/policy.json

echo "✅ Rol IAM creado: $ROLE_NAME"

# Esperar a que el rol esté disponible
sleep 10

# ===== 5. CREAR/ACTUALIZAR LAMBDA LAYER =====
echo ""
echo "📤 Subiendo Lambda Layer..."

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

LAYER_RESPONSE=$(aws lambda publish-layer-version \
  --layer-name "$LAYER_NAME" \
  --zip-file fileb://lambda_layer.zip \
  --compatible-runtimes python3.11 \
  --region "$REGION" 2>/dev/null || echo "{}")

LAYER_ARN=$(echo "$LAYER_RESPONSE" | grep -o '"LayerVersionArn":"[^"]*"' | cut -d'"' -f4)

if [ -z "$LAYER_ARN" ]; then
  echo "⚠️  Usando layer existente"
  LAYER_ARN=$(aws lambda list-layer-versions --layer-name "$LAYER_NAME" --region "$REGION" --query 'LayerVersions[0].LayerVersionArn' --output text)
fi

echo "✅ Layer ARN: $LAYER_ARN"

# ===== 6. CREAR/ACTUALIZAR FUNCIÓN LAMBDA =====
echo ""
echo "📤 Desplegando función Lambda..."

FUNCTION_EXISTS=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null || echo "")

if [ -z "$FUNCTION_EXISTS" ]; then
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --role "$ROLE_ARN" \
    --handler lambda_handler.lambda_handler \
    --zip-file fileb://lambda_function.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment "Variables={BUCKET_NAME=$BUCKET_NAME}" \
    --layers "$LAYER_ARN" \
    --region "$REGION"
else
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://lambda_function.zip \
    --region "$REGION"
  
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment "Variables={BUCKET_NAME=$BUCKET_NAME}" \
    --layers "$LAYER_ARN" \
    --region "$REGION"
fi

echo "✅ Función Lambda desplegada"

# ===== 7. CREAR EVENTBRIDGE RULE (CRON) =====
echo ""
echo "⏰ Configurando EventBridge (cron diario)..."

# Obtener AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
RULE_NAME="${PROJECT_NAME}-daily-trigger"
FUNCTION_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

# Crear o actualizar regla
aws events put-rule \
  --name "$RULE_NAME" \
  --schedule-expression "cron(8 0 * * ? *)" \
  --state ENABLED \
  --description "Ejecuta análisis de apuestas diariamente a las 8:00 AM UTC" \
  --region "$REGION" 2>/dev/null || true

# Permitir EventBridge invocar Lambda
aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "${PROJECT_NAME}-eventbridge-trigger" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}" \
  --region "$REGION" 2>/dev/null || true

# Añadir target
aws events put-targets \
  --rule "$RULE_NAME" \
  --targets "Id"="1","Arn"="$FUNCTION_ARN","RoleArn"="arn:aws:iam::${ACCOUNT_ID}:role/service-role/EventBridgeInvokeLambdaRole" \
  --region "$REGION" 2>/dev/null || true

# Crear rol para EventBridge si no existe
aws iam create-role \
  --role-name EventBridgeInvokeLambdaRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "events.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' --region "$REGION" 2>/dev/null || true

echo "✅ EventBridge configurado (diariamente a las 8:00 AM UTC)"

# ===== 8. HACER BUCKET S3 PÚBLICO (opcional) =====
echo ""
echo "🌐 Configurando acceso público a reportes..."

BUCKET_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::'$BUCKET_NAME'/reportes/*"
    }
  ]
}'

echo "$BUCKET_POLICY" > /tmp/bucket_policy.json
aws s3api put-bucket-policy --bucket "$BUCKET_NAME" --policy file:///tmp/bucket_policy.json

echo "✅ Bucket público configurado"

# ===== RESUMEN =====
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           ✅ DEPLOYMENT COMPLETADO EXITOSAMENTE              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 CONFIGURACIÓN:"
echo "  • Función Lambda: $FUNCTION_NAME"
echo "  • Región: $REGION"
echo "  • Bucket S3: $BUCKET_NAME"
echo "  • Ejecución: Diariamente 8:00 AM UTC"
echo ""
echo "💰 COSTO ESTIMADO:"
echo "  • Lambda: ~$0.00 (1M requests/mes gratis)"
echo "  • EventBridge: ~$0.00 (14M eventos/mes gratis)"
echo "  • S3: ~$0.02-0.20 (5GB gratis)"
echo "  • Total: ~$0.20/mes"
echo ""
echo "🔗 REPORTES:"
echo "  • URL: https://${BUCKET_NAME}.s3.amazonaws.com/reportes/YYYY-MM-DD.html"
echo ""
echo "🧪 PRUEBA LA FUNCIÓN:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --region $REGION /tmp/output.json"
echo ""
echo "📚 VER LOGS:"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --region $REGION --follow"
echo ""

# Limpiar archivos temporales
rm -rf lambda_build lambda_function /tmp/policy.json /tmp/bucket_policy.json

echo "✨ ¡Listo! Tu solución está corriendo en AWS"
