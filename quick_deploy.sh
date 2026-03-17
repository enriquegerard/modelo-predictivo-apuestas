#!/bin/bash

# GUÍA RÁPIDA DE DEPLOYMENT A AWS
# Solución más barata: ~$0.20/mes

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║    DEPLOYMENT A AWS FREE TIER - GUÍA RÁPIDA                  ║"
echo "║                                                                ║"
echo "║    Costo: ~$0.20/mes | Lambda + EventBridge + S3             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Verificar si AWS CLI está instalado
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI no está instalado"
    echo ""
    echo "Instálalo con:"
    echo "  • macOS:  brew install awscli"
    echo "  • Linux:  sudo apt-get install awscli"
    echo "  • Otros:  pip install awscli"
    exit 1
fi

# Verificar si está configurado
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI no está configurado"
    echo ""
    echo "Configúralo con:"
    echo "  aws configure"
    echo ""
    echo "Necesitarás:"
    echo "  • AWS Access Key ID"
    echo "  • AWS Secret Access Key"
    echo "  • Región: us-east-1 (Free Tier)"
    echo ""
    exit 1
fi

ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text)
echo "✅ AWS CLI configurado correctamente"
echo "   Cuenta: $ACCOUNT"
echo ""

# Menú interactivo
echo "¿Qué quieres hacer?"
echo ""
echo "1) 📦 Deployment inicial (crear todo)"
echo "2) 🔄 Actualizar función Lambda (sin recrear)"
echo "3) 🧪 Ejecutar función manualmente"
echo "4) 📊 Ver logs de ejecuciones"
echo "5) 🗑️  Limpiar y eliminar recursos"
echo "6) 📋 Ver estado actual"
echo ""
read -p "Selecciona opción (1-6): " option

case $option in
  1)
    echo ""
    echo "🚀 Iniciando deployment..."
    echo ""
    
    # Verificar si ya existe
    if aws lambda get-function --function-name daily-betting-analysis --region us-east-1 &>/dev/null; then
      echo "⚠️  Ya existe una función Lambda llamada 'daily-betting-analysis'"
      read -p "¿Deseas recrearla? (s/N): " confirm
      if [[ ! $confirm =~ ^[Ss]$ ]]; then
        echo "Operación cancelada"
        exit 0
      fi
    fi
    
    ./aws_deploy.sh
    ;;
    
  2)
    echo ""
    echo "🔄 Actualizando código Lambda..."
    
    FUNCTION_NAME="daily-betting-analysis"
    REGION="us-east-1"
    
    # Preparar código
    mkdir -p lambda_function
    cp -r src lambda_function/ 2>/dev/null
    cp .env.example lambda_function/.env 2>/dev/null
    
    # Crear ZIP
    cd lambda_function
    zip -r -q ../lambda_function_update.zip . -x "*.git*" "__pycache__/*"
    cd ..
    
    # Actualizar
    aws lambda update-function-code \
      --function-name "$FUNCTION_NAME" \
      --zip-file fileb://lambda_function_update.zip \
      --region "$REGION"
    
    echo "✅ Función actualizada correctamente"
    
    # Limpiar
    rm -rf lambda_function lambda_function_update.zip
    ;;
    
  3)
    echo ""
    echo "🧪 Ejecutando función manualmente..."
    
    FUNCTION_NAME="daily-betting-analysis"
    REGION="us-east-1"
    
    echo "Invocando función..."
    aws lambda invoke \
      --function-name "$FUNCTION_NAME" \
      --region "$REGION" \
      --log-type Tail \
      /tmp/lambda_response.json \
      --query 'LogResult' \
      --output text | base64 -d
    
    echo ""
    echo "Respuesta completa:"
    cat /tmp/lambda_response.json | python3 -m json.tool
    ;;
    
  4)
    echo ""
    echo "📊 Mostrando logs (Ctrl+C para salir)..."
    echo ""
    
    aws logs tail /aws/lambda/daily-betting-analysis \
      --region us-east-1 \
      --follow \
      --format short
    ;;
    
  5)
    echo ""
    echo "🗑️  Iniciando limpieza..."
    ./aws_cleanup.sh
    ;;
    
  6)
    echo ""
    echo "📋 Estado actual de la solución:"
    echo ""
    
    REGION="us-east-1"
    ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text)
    
    # Lambda
    echo "▸ Función Lambda:"
    if aws lambda get-function --function-name daily-betting-analysis --region "$REGION" &>/dev/null; then
      aws lambda get-function --function-name daily-betting-analysis --region "$REGION" \
        --query 'Configuration.[FunctionName,Runtime,MemorySize,Timeout]' \
        --output text | awk '{print "    Nombre: " $1 "\n    Runtime: " $2 "\n    Memoria: " $3 " MB\n    Timeout: " $4 " seg"}'
    else
      echo "    ❌ No existe"
    fi
    
    # EventBridge
    echo ""
    echo "▸ EventBridge Rule:"
    if aws events describe-rule --name betting-analyzer-daily-trigger --region "$REGION" &>/dev/null; then
      RULE=$(aws events describe-rule --name betting-analyzer-daily-trigger --region "$REGION")
      SCHEDULE=$(echo "$RULE" | grep -o '"ScheduleExpression":"[^"]*"' | cut -d'"' -f4)
      echo "    Activa ✅"
      echo "    Schedule: $SCHEDULE"
    else
      echo "    ❌ No existe"
    fi
    
    # S3
    echo ""
    echo "▸ Buckets S3:"
    BUCKETS=$(aws s3 ls --region "$REGION" | grep betting-analyzer | wc -l)
    if [ "$BUCKETS" -gt 0 ]; then
      aws s3 ls --region "$REGION" | grep betting-analyzer
    else
      echo "    ❌ No existen"
    fi
    
    # IAM Roles
    echo ""
    echo "▸ Roles IAM:"
    if aws iam get-role --role-name betting-analyzer-lambda-role &>/dev/null; then
      echo "    betting-analyzer-lambda-role ✅"
    else
      echo "    betting-analyzer-lambda-role ❌"
    fi
    
    echo ""
    ;;
    
  *)
    echo "Opción no válida"
    exit 1
    ;;
esac
