# Guía manual en AWS Console (UI)

Objetivo: desplegar el proyecto de forma manual en la interfaz de AWS para entender exactamente qué automatiza el script.

---

## 1) Arquitectura y qué hace cada servicio

### Amazon S3
- Qué es: almacenamiento de archivos.
- Qué hará aquí: guardar los reportes HTML diarios.
- Resultado: tendrás URLs para abrir reportes en navegador.

### AWS Lambda
- Qué es: ejecución de código sin servidor.
- Qué hará aquí: ejecutar el análisis diario (`python -m src.app today --date ... --html`) y subir el HTML a S3.

### Amazon EventBridge (Scheduler)
- Qué es: planificador de eventos (cron).
- Qué hará aquí: disparar Lambda 1 vez al día a la hora que definas.

### AWS IAM
- Qué es: permisos y seguridad.
- Qué hará aquí: crear un rol para que Lambda pueda escribir logs y subir archivos a S3.

### Amazon CloudWatch Logs
- Qué es: logs y monitoreo.
- Qué hará aquí: guardar salida/errores de Lambda para debug.

### (Opcional) Amazon SNS
- Qué es: notificaciones.
- Qué haría aquí: enviar email cuando termine el reporte.

---

## 2) Prerrequisitos antes de entrar a AWS

- Tener cuenta AWS activa.
- Tener tu proyecto listo localmente.
- Tener un ZIP del código (incluyendo `src/` y `lambda_handler.py`).
- Tener otro ZIP con dependencias si usas Layer (recomendado).

Sugerencia simple:
- Runtime: Python 3.11.
- Región: `us-east-1` (suele usarse para Free Tier).

---

## 3) Paso a paso manual en UI

## Paso A: Crear bucket S3

1. En AWS Console abre S3.
2. Click Create bucket.
3. Nombre único, por ejemplo: `betting-analyzer-<tu-sufijo>`.
4. Región: la misma que usarás para Lambda.
5. Deja defaults y crea.

Si quieres abrir reportes por URL pública:
6. En el bucket entra a Permissions.
7. Desactiva Block all public access (solo si entiendes el riesgo).
8. Agrega Bucket policy para lectura pública de `reportes/*`.

Ejemplo de política (reemplaza bucket):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadReports",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::TU_BUCKET/reportes/*"
    }
  ]
}
```

---

## Paso B: Crear rol IAM para Lambda

1. Abre IAM.
2. Roles -> Create role.
3. Trusted entity: AWS service.
4. Use case: Lambda.
5. Adjunta políticas:
   - `AWSLambdaBasicExecutionRole` (logs en CloudWatch).
6. Crea el rol, por ejemplo: `betting-analyzer-lambda-role`.

Luego agrega permiso S3 específico:
7. En el rol -> Add permissions -> Create inline policy.
8. JSON policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::TU_BUCKET/reportes/*"
    }
  ]
}
```

9. Guardar policy (ejemplo nombre: `s3-reports-access`).

---

## Paso C: Crear Lambda Layer (dependencias)

Úsalo si tu función necesita librerías como `pandas`, `requests`, `rich`.

1. Ve a Lambda -> Layers -> Create layer.
2. Nombre: `betting-dependencies`.
3. Sube ZIP del layer (estructura de Python para 3.11).
4. Compatible runtimes: Python 3.11.
5. Create.

Nota: si no usas layer, debes empaquetar dependencias dentro del ZIP de la función.

---

## Paso D: Crear función Lambda

1. Lambda -> Create function.
2. Author from scratch.
3. Function name: `daily-betting-analysis`.
4. Runtime: Python 3.11.
5. Execution role: Use an existing role.
6. Selecciona `betting-analyzer-lambda-role`.
7. Create function.

Configura la función:
8. En Code sube tu ZIP de función.
9. En Runtime settings verifica handler (`lambda_handler.lambda_handler`).
10. En Configuration -> Environment variables agrega:
    - `BUCKET_NAME` = tu bucket S3
11. En Configuration -> General configuration:
    - Timeout: 300s
    - Memory: 512 MB
12. En Layers -> Add a layer -> selecciona `betting-dependencies`.

---

## Paso E: Probar Lambda manualmente

1. En Lambda click Test.
2. Crea evento test con payload:

```json
{
  "date": "2026-03-17"
}
```

3. Ejecuta test.
4. Verifica:
   - respuesta HTTP 200,
   - logs sin error,
   - objeto en S3: `reportes/2026-03-17.html`.

---

## Paso F: Programar ejecución diaria (EventBridge)

1. Ve a EventBridge -> Rules -> Create rule.
2. Nombre: `betting-analyzer-daily-trigger`.
3. Rule type: Schedule.
4. Schedule pattern: Cron expression.
5. Ejemplo diario 08:00 UTC:
   - `cron(0 8 * * ? *)`
6. Target: Lambda function.
7. Selecciona `daily-betting-analysis`.
8. Create rule.

Listo: desde aquí corre automático todos los días.

---

## Paso G: Ver logs y monitoreo

1. CloudWatch -> Log groups.
2. Abre `/aws/lambda/daily-betting-analysis`.
3. Revisa cada ejecución:
   - duración,
   - errores,
   - salida de tu script.

Puedes crear alarmas si hay errores seguidos.

---

## 4) Qué está automatizando el script exactamente

El script te evita hacer manualmente:
- Crear bucket S3.
- Crear rol IAM + policy inline para S3.
- Publicar Layer con dependencias.
- Crear/actualizar Lambda.
- Setear variables de entorno.
- Configurar EventBridge cron.
- Configurar permisos de invocación entre EventBridge y Lambda.

En UI haces todo eso con clicks y formularios.

---

## 5) Costos Free Tier (resumen realista)

Para 1 ejecución diaria:
- Lambda: normalmente dentro de free tier.
- EventBridge: normalmente dentro de free tier.
- S3: normalmente dentro de free tier si no guardas miles de reportes pesados.
- CloudWatch Logs: muy bajo, pero vigílalo.

Recomendación: poner retención de logs (7-14 días) para evitar acumulación.

---

## 6) Errores comunes y cómo corregir

### Error AccessDenied en S3
- Falta permiso `s3:PutObject` en el rol de Lambda.
- Revisa que el ARN del bucket/prefijo coincida exactamente.

### Lambda timeout
- Sube timeout (por ejemplo 300s a 600s).
- Reduce trabajo dentro de la función.

### No se dispara en horario esperado
- Cron de EventBridge está en UTC.
- Convierte tu hora local a UTC.

### No aparece archivo en S3
- Revisa logs en CloudWatch.
- Verifica variable `BUCKET_NAME`.

---

## 7) Flujo mental final (simple)

1. EventBridge despierta Lambda cada día.
2. Lambda corre tu análisis.
3. Lambda genera HTML y lo sube a S3.
4. S3 sirve el reporte por URL.
5. CloudWatch guarda trazas para soporte.

---

## 8) Recomendación para aprender rápido

Haz primero 1 despliegue manual completo en UI.
Después usa script para el resto.

Así entiendes arquitectura + automatización.
