#!/bin/bash

# Script para destruir la solución en AWS (eliminar costos)

echo "🗑️  Iniciando limpieza de recursos AWS..."

REGION="us-east-1"
PROJECT_NAME="betting-analyzer"
FUNCTION_NAME="daily-betting-analysis"
RULE_NAME="${PROJECT_NAME}-daily-trigger"
ROLE_NAME="${PROJECT_NAME}-lambda-role"
LAYER_NAME="betting-dependencies"

# Función para confirmar
confirm() {
  read -p "¿Confirmas? (s/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Ss]$ ]]; then
    return 0
  else
    return 1
  fi
}

echo ""
echo "⚠️  ESTO ELIMINARÁ:"
echo "  • Función Lambda: $FUNCTION_NAME"
echo "  • EventBridge Rule: $RULE_NAME"
echo "  • Rol IAM: $ROLE_NAME"
echo "  • Layer Lambda: $LAYER_NAME"
echo "  • Los reportes en S3 se mantendrán (debes eliminarlos manualmente)"
echo ""

if confirm; then
  echo ""
  echo "Eliminando EventBridge Rule..."
  aws events remove-targets --rule "$RULE_NAME" --region "$REGION" --ids "1" 2>/dev/null
  aws events delete-rule --name "$RULE_NAME" --region "$REGION" 2>/dev/null
  
  echo "Eliminando función Lambda..."
  aws lambda delete-function --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null
  
  echo "Eliminando Layer..."
  LAYER_VERSION=$(aws lambda list-layer-versions --layer-name "$LAYER_NAME" --region "$REGION" --query 'LayerVersions[0].Version' --output text)
  aws lambda delete-layer-version --layer-name "$LAYER_NAME" --version-number "$LAYER_VERSION" --region "$REGION" 2>/dev/null || true
  
  echo "Eliminando Rol IAM..."
  aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "${PROJECT_NAME}-s3-policy" 2>/dev/null
  aws iam delete-role --role-name "$ROLE_NAME" 2>/dev/null
  
  echo "Eliminando Rol EventBridge..."
  aws iam delete-role-policy --role-name EventBridgeInvokeLambdaRole --policy-name "${PROJECT_NAME}-eventbridge-policy" 2>/dev/null || true
  aws iam delete-role --role-name EventBridgeInvokeLambdaRole 2>/dev/null || true
  
  echo ""
  echo "✅ Limpieza completada"
  echo ""
  echo "⚠️  Para eliminar completamente los costos, también debes:"
  echo "  • Vaciar y eliminar el bucket S3"
  echo "  • Ver el nombre del bucket en la salida del deployment"
  echo ""
else
  echo "Operación cancelada"
fi
