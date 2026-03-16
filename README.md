# Analizador local de cuotas de fútbol (educativo)

Herramienta local para **análisis educativo** y **paper trading** (simulación).  
**No** genera recomendaciones reales ni asesoría de apuestas.

> **Aviso importante:** esta es una herramienta educativa, no asesoría de apuestas.

## Qué hace este MVP

- Ejecuta en local con Python 3.11+.
- Obtiene partidos (fixtures/resultados) desde API de fútbol o modo mock.
- Obtiene cuotas 1X2 desde API de odds o modo mock.
- Calcula:
  - Probabilidad implícita normalizada por overround.
  - Probabilidad del modelo (Poisson simple).
  - `edge = prob_modelo - prob_implicita`.
  - `score` de interés para priorización analítica.
- Simulación tipo paper trading:
  - bankroll ficticio,
  - staking fijo,
  - tracking en SQLite,
  - liquidación con resultado API o carga manual JSON.

## Modelo elegido: Poisson (simple)

Se usa Poisson porque en un MVP rápido permite estimar $P(1)$, $P(X)$ y $P(2)$ desde goles esperados:

- $\lambda_{home}$ y $\lambda_{away}$ se derivan de promedios de liga y fuerzas ataque/defensa por equipo.
- Se calcula una matriz de probabilidades de goles $0..6$ y se agrega:
  - local gana: $i > j$
  - empate: $i = j$
  - visitante gana: $i < j$

Es una base didáctica, no un modelo de producción.

## Estructura

- [src/config.py](src/config.py)
- [src/clients/matches_client.py](src/clients/matches_client.py)
- [src/clients/odds_client.py](src/clients/odds_client.py)
- [src/models/poisson.py](src/models/poisson.py)
- [src/analysis/implied_probs.py](src/analysis/implied_probs.py)
- [src/analysis/edge_ranker.py](src/analysis/edge_ranker.py)
- [src/storage/db.py](src/storage/db.py)
- [src/app.py](src/app.py)
- [data/mock_matches.json](data/mock_matches.json)
- [data/mock_odds.json](data/mock_odds.json)
- [requirements.txt](requirements.txt)

## Instalación paso a paso

1. Crear y activar entorno virtual:
   - macOS/Linux:
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`

2. Instalar dependencias:
   - `pip install -r requirements.txt`

3. Configurar variables de entorno:
  - Copia [.env.example](.env.example) a `.env`.
   - Para empezar rápido, deja `MOCK_MODE=true`.

## Configuración `.env`

Variables principales:

- `MOCK_MODE=true|false`
- `FOOTBALL_DATA_API_KEY` (API de partidos/resultados)
- `THE_ODDS_API_KEY` (API de cuotas)
- `LEAGUES=PL,PD,SA`
- `ODDS_SPORTS=soccer_epl,soccer_spain_la_liga,soccer_italy_serie_a`
- `TIMEZONE=Europe/Madrid`
- `CACHE_TTL_MINUTES=15`

## Comandos

### 1) Ranking diario

```bash
python -m src.app today
python -m src.app today --date 2026-03-16
```

Salida en tabla con columnas:

- `League`
- `Match`
- `StartTime`
- `BestOddsHome/Draw/Away`
- `ImpliedHome/Draw/Away`
- `ModelHome/Draw/Away`
- `EdgeMax`
- `Score`

### 2) Simulación (paper trading)

```bash
python -m src.app simulate --date 2026-03-16
```

Parámetros útiles:

- `--bankroll 100`
- `--stake 1`
- `--min-edge 0.02`
- `--manual-results data/manual_results_example.json`

Ejemplo completo:

```bash
python -m src.app simulate --date 2026-03-16 --bankroll 100 --stake 1 --manual-results data/manual_results_example.json
```

### 3) Backtest simple

```bash
python -m src.app backtest --start 2026-03-16 --end 2026-03-17
```

Con resultados manuales:

```bash
python -m src.app backtest --start 2026-03-16 --end 2026-03-17 --manual-results data/manual_results_example.json
```

## Cache, errores y resiliencia

- Cache local SQLite con TTL de 15 minutos (`api_cache`).
- Rate limiting simple por cliente (`MIN_REQUEST_INTERVAL_SEC`).
- Retries con backoff para `timeout`, `429` y errores `5xx`.

## Persistencia local

Se crea SQLite en `data/app.db` con:

- `api_cache`: respuestas de API cacheadas.
- `simulation_positions`: posiciones de simulación y estado (`PENDING` / `SETTLED`).

## Modo mock (sin API keys)

Si `MOCK_MODE=true` o faltan keys:

- Partidos desde [data/mock_matches.json](data/mock_matches.json)
- Cuotas desde [data/mock_odds.json](data/mock_odds.json)

Esto permite ejecutar el MVP de extremo a extremo sin dependencias externas.

## Notas finales

- Uso exclusivo para análisis educativo y simulación.
- No incluye lenguaje de recomendación operativa real.
- Puedes ampliar luego con features de ingeniería (tests, logging estructurado, validación de esquemas, métricas).
