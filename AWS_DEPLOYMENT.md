# Deployment a AWS (Free Tier) - Solución Más Barata

## 💰 Costo Mensual: ~$0.20 USD

### Componentes:
- **Lambda** (1M requests/mes gratis)
- **EventBridge** (14M eventos/mes gratis)
- **S3** (5GB gratis)
- **CloudWatch Logs** (Gratis para Free Tier)

---

## 📋 Prerequisitos

1. **Cuenta AWS** con Free Tier activo
2. **AWS CLI** instalado y configurado
   ```bash
   # Instalar AWS CLI
   brew install awscli  # macOS
   # o
   pip install awscli
   
   # Configurar credenciales
   aws configure
   ```

3. **Permisos IAM mínimos** necesarios:
   - `lambda:*`
   - `iam:*`
   - `s3:*`
   - `events:*`
   - `logs:*`

---

## 🚀 Instalación en 1 Comando

```bash
# Desde el directorio raíz del proyecto
chmod +x aws_deploy.sh
./aws_deploy.sh
```

El script automáticamente:
1. ✅ Crea bucket S3 para guardar reportes
2. ✅ Empaqueta dependencias Python en Lambda Layer
3. ✅ Crea función Lambda optimizada
4. ✅ Configura roles IAM con permisos mínimos
5. ✅ Crea EventBridge Rule (cron diario)
6. ✅ Configura acceso público a reportes
7. ✅ Prueba la configuración

---

## ⏰ Cronograma

**Ejecución:** Diariamente a las **8:00 AM UTC**

Para cambiar la hora, edita el script y modifica:
```bash
--schedule-expression "cron(8 0 * * ? *)"
# Formato: cron(minutos horas día mes ? año)
# Ejemplos:
# cron(0 6 * * ? *)   = 6:00 AM UTC
# cron(0 12 * * ? *)  = 12:00 PM UTC
# cron(0 18 * * ? *)  = 6:00 PM UTC
```

---

## 🧪 Pruebas

### Ejecutar manualmente la función:
```bash
aws lambda invoke \
  --function-name daily-betting-analysis \
  --region us-east-1 \
  /tmp/output.json

cat /tmp/output.json
```

### Ver logs en tiempo real:
```bash
aws logs tail /aws/lambda/daily-betting-analysis --region us-east-1 --follow
```

### Listar reportes generados:
```bash
aws s3 ls s3://betting-analyzer-XXXX/reportes/ --region us-east-1
```

---

## 📊 Monitorear Ejecuciones

### CloudWatch Dashboard (AWS Console):
```
https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/daily-betting-analysis
```

### Métricas automáticas:
- **Invocaciones**: Diarias (30/mes)
- **Duración**: ~5-10 segundos
- **Errores**: Monitoreados en CloudWatch

---

## 🔗 Acceder a Reportes

Cada reporte se guarda públicamente en:
```
https://betting-analyzer-XXXX.s3.amazonaws.com/reportes/2026-03-17.html
```

El nombre del bucket aparece en la salida del deployment.

---

## 📧 Notificaciones (Opcional)

Para recibir email cuando termina el reporte:

```bash
# Crear SNS Topic
aws sns create-topic --name betting-alerts --region us-east-1

# Suscribirse
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:betting-alerts \
  --protocol email \
  --notification-endpoint tu@email.com
```

Luego, edita el Lambda handler para enviar notificación:
```python
sns = boto3.client('sns')
sns.publish(
    TopicArn='arn:aws:sns:us-east-1:ACCOUNT_ID:betting-alerts',
    Subject='Reporte de Apuestas Generado',
    Message=f'Reporte disponible: {html_url}'
)
```

---

## 🗑️ Eliminar (Limpieza)

Para detener costos (aunque sea gratis):

```bash
chmod +x aws_cleanup.sh
./aws_cleanup.sh
```

Luego elimina el bucket S3 manualmente:
```bash
# Ver buckets
aws s3 ls

# Vaciar bucket
aws s3 rm s3://betting-analyzer-XXXX --recursive

# Eliminar bucket
aws s3 rb s3://betting-analyzer-XXXX
```

---

## 🐛 Troubleshooting

### Error: "Access Denied"
```bash
# Verifica tus credenciales AWS
aws sts get-caller-identity
```

### Función no ejecuta
```bash
# Ver logs
aws logs tail /aws/lambda/daily-betting-analysis --region us-east-1

# Invocar manualmente para debug
aws lambda invoke \
  --function-name daily-betting-analysis \
  --log-type Tail \
  /tmp/response.json \
  --region us-east-1
```

### Timeout (> 300 segundos)
Aumenta timeout en Lambda Console:
- Function → Configuration → General → Timeout (máximo 900 seg)

### S3 bucket "already exists"
El script reutiliza buckets existentes. Para usar uno nuevo, especifica:
```bash
BUCKET_NAME="my-custom-bucket-name" ./aws_deploy.sh
```

---

## 💡 Alternativas (Más caras pero más simples)

### Opción 2: EC2 t2.micro + Cron
- **Costo**: ~$2-3/mes
- **Ventaja**: Más control, sin capas
- **Desventaja**: Máquina siempre activa

### Opción 3: GitHub Actions
- **Costo**: Gratis para repositorios públicos
- **Ventaja**: Integrado con GitHub
- **Desventaja**: Requiere repositorio público

---

## 📞 Soporte

Para actualizar la función sin redeployar:
```bash
# Update code only
aws lambda update-function-code \
  --function-name daily-betting-analysis \
  --zip-file fileb://lambda_function.zip \
  --region us-east-1

# Update environment variables
aws lambda update-function-configuration \
  --function-name daily-betting-analysis \
  --environment Variables={BUCKET_NAME=my-bucket} \
  --region us-east-1
```

---

## ✅ Checklist de Éxito

- [ ] AWS CLI instalado y configurado
- [ ] Script aws_deploy.sh ejecutado sin errores
- [ ] Lambda function visible en AWS Console
- [ ] EventBridge Rule creada
- [ ] Bucket S3 creado
- [ ] Primer reporte generado (manual test)
- [ ] Logs aparecen en CloudWatch

---

**Última actualización**: 2026-03-16
**Versión**: 1.0
