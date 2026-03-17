# 🚀 SOLUCIÓN AWS LISTA PARA DEPLOYAR

## 📦 Archivos Creados

```
├── aws_deploy.sh              ⭐ Script principal de deployment
├── aws_cleanup.sh             🗑️  Script para limpiar recursos
├── quick_deploy.sh            ⚡ Menú interactivo (recomendado)
├── aws_config.env             ⚙️  Configuración personalizable
└── AWS_DEPLOYMENT.md          📚 Documentación completa
```

---

## 🎯 INICIO RÁPIDO

### Opción 1: Menú Interactivo (RECOMENDADO)
```bash
cd /Users/gerardo/Desktop/modelo-predictivo-apuestas
./quick_deploy.sh
```

### Opción 2: Deployment Automático Directo
```bash
cd /Users/gerardo/Desktop/modelo-predictivo-apuestas
./aws_deploy.sh
```

---

## ✅ CHECKLIST PRE-DEPLOYMENT

Antes de ejecutar, verifica:

- [ ] **AWS CLI instalado**: `aws --version`
- [ ] **Credenciales configuradas**: `aws configure`
- [ ] **Usar región Free Tier**: `us-east-1`
- [ ] **Tener permisos IAM**:
  - Lambda
  - S3
  - EventBridge
  - IAM
  - CloudWatch Logs
- [ ] **Python 3.11+**: `python3 --version`
- [ ] **Pip actualizado**: `pip install --upgrade pip`

---

## 💡 WHAT'S INSIDE

### `aws_deploy.sh` - Lo que hace:

1. **Crea S3 Bucket** para guardar reportes HTML
2. **Empaqueta dependencias** (requests, pandas, etc.)
3. **Crea Lambda Layer** con todas las librerías
4. **Sube función Lambda** con tu código
5. **Configura IAM Roles** con permisos mínimos
6. **Crea EventBridge Rule** para ejecutar diariamente a las 8:00 AM UTC
7. **Configura acceso público** a los reportes
8. **Genera URLs públicas** para acceder a reportes

### `quick_deploy.sh` - Menú Interactivo:

Permite:
- ✅ Deployment inicial
- 🔄 Actualizar código sin recrear
- 🧪 Ejecutar función manualmente
- 📊 Ver logs en tiempo real
- 🗑️  Limpiar recursos
- 📋 Ver estado actual

---

## 💰 COSTO ESTIMADO

| Servicio | Gratis/mes | Tu Uso (30 días) | Costo |
|----------|-----------|-----------------|-------|
| Lambda | 1M requests | 30 llamadas | $0.00 |
| EventBridge | 14M eventos | 30 eventos | $0.00 |
| S3 | 5 GB | ~100 MB | $0.00 |
| CloudWatch | Algunos gratis | Mínimo | $0.02-0.20 |
| **TOTAL** | | | **$0.20/mes** |

---

## ⏰ EJECUCIÓN AUTOMÁTICA

La función se ejecuta:
- **Hora**: 8:00 AM UTC (puedes cambiar en `aws_deploy.sh`)
- **Frecuencia**: Diariamente
- **Duración**: ~5-10 segundos
- **Reportes guardados**: `https://BUCKET_NAME.s3.amazonaws.com/reportes/YYYY-MM-DD.html`

---

## 🔧 CONFIGURACIÓN PERSONALIZADA

Edita `aws_config.env` para:
- Cambiar hora de ejecución
- Ajustar memoria/timeout de Lambda
- Configurar retención de logs
- Habilitar notificaciones por email
- Agregar tags para facturación

---

## 📊 MONITOREO

Después del deployment:

### Ver ejecuciones:
```bash
aws logs tail /aws/lambda/daily-betting-analysis --follow
```

### Listar reportes:
```bash
aws s3 ls s3://betting-analyzer-*/reportes/
```

### Invocar manualmente:
```bash
aws lambda invoke --function-name daily-betting-analysis /tmp/out.json
cat /tmp/out.json | python3 -m json.tool
```

---

## 🗑️ LIMPIAR (SI NO QUIERES MÁS)

```bash
./aws_cleanup.sh
```

O manualmente:
```bash
# Eliminar bucket
aws s3 rb s3://betting-analyzer-XXXX --force

# Eliminar Lambda
aws lambda delete-function --function-name daily-betting-analysis

# Eliminar EventBridge
aws events delete-rule --name betting-analyzer-daily-trigger

# Eliminar Roles
aws iam delete-role --role-name betting-analyzer-lambda-role
```

---

## 🆘 TROUBLESHOOTING

### Error: "Access Denied"
```bash
aws sts get-caller-identity
# Verifica que tengas permisos en AWS Console
```

### Función no ejecuta
```bash
# Ver logs detallados
aws logs tail /aws/lambda/daily-betting-analysis --region us-east-1

# Invocar manualmente con logs
aws lambda invoke \
  --function-name daily-betting-analysis \
  --log-type Tail \
  /tmp/response.json \
  --region us-east-1
cat /tmp/response.json
```

### Bucket "already exists"
```bash
# El script reutiliza buckets existentes
# Para crear uno nuevo:
BUCKET_NAME="mi-bucket-$(date +%s)" ./aws_deploy.sh
```

### Timeout
Si tarda más de 5 minutos, aumenta timeout:
- AWS Console → Lambda → daily-betting-analysis → Configuration → Timeout

---

## 📚 REFERENCIAS

- **AWS Lambda**: https://docs.aws.amazon.com/lambda/
- **EventBridge**: https://docs.aws.amazon.com/eventbridge/
- **S3**: https://docs.aws.amazon.com/s3/
- **AWS Free Tier**: https://aws.amazon.com/free/

---

## ✨ PRÓXIMOS PASOS

1. **Ejecuta**: `./quick_deploy.sh`
2. **Espera**: ~2-3 minutos
3. **Recibe**: Email con reportes diarios
4. **Disfruta**: Análisis automático 24/7 en Free Tier

---

**¡Listo para deployar! 🚀**
