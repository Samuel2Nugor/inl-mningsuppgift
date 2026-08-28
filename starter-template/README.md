# Starter Template – IoT Telemetry & Analytics Platform

REST API för mottagning och lagring av telemetridata från IoT-sensorer. Byggd med Flask, PostgreSQL och Docker Compose enligt ett OpenAPI 3.0-kontrakt.

## Arkitektur

- **api** - Flask-baserat REST API (Python 3.11), körs som icke-root (USER 100)
- **db** - PostgreSQL 15, data persisteras via Docker-volym 'postgres_data'
- **test** - Schemathesis, kör automatiserad kontrakstestning mot API:et

## Nätverk

- 'frontend' - exponerar API:et mot värddatorn (port 5000)
- 'backend' - internt nätverk ('internal: true'), används för trafik mellan   API och databas. Databasen är inte åtkomlig utifrån.

## Endpoints

| Metod | Path | Beskrivning |
|-------|------|-------------|
| GET | '/health' | Hälsokontroll, returnerar ' {"status": "healthy"}'  |
| GET | '/openapi.json' | Exponerar OpenAPI-kontraktet i JSON-format |
| GEt | '/api/v1/telemetry' | Hämtar alla telemtriposter |
| POST | '/api/v1/telemetry' | Sparar ny telemetripost |

### POST-payload

```json
{
   "sensor_id": "temp-sensor-01",
   "metric_type": "temperature",
   "value": 22.5,
   "timestamp": "20026-08-19T20:00:00Z"
}
````

'sensor_id', 'metric_type' och 'value' är obligatosriska. 'timestamp' är valfri - utelämnas den sätts 'CURRENT_TIMESTAMP' av databasen.

## Bygg och kör

```bash
cd starter-template
docker-compose up --build -d
````

Kontrollera status:

```bash
docker-compose ps
```

'db' ska vara 'healthy' och 'api' ska vara 'Up'. API:et strtar först när databasens healthcheck ('pg-isready') har gått igenom, via 'depends_on: condition: service_health'


## Kör kontrakstester

```bash
docker-compose run tests
```

Schemathesis läser kontraktet från 'http://api:5000/openapi.json' och kör Examples-, Coverage- och Fuzzing-faserna. Förväntat resultat: inga Kontraksöverträdelser.

## Städa upp

```bash
docker-compose down -v
```

'-v' tar bort volymen 'postgres_data'. Utelämna flaggan om lagrad data ska behållas mellan omstarter.


## Implementationsnoteringar

- 'timestamp' lagras som 'TIMESTAMPTZ' för att bevara tidszonsinformation. naiva tidstämplar skulle brutit mot 'format: date-time' i kontraktet.

- Inkommande payload valideras på typnivå innan databasanrop. fel typ ger '400', inte '500'. Detta gäller payloadens struktur (måste varra ett JSON-objekt), 'value' (numeriskt, inte boolean), 'sensor_id'/'metric_type' (strängar) samt 'timestamp' (parsbar ISO 8601 med rimlig UTC-ofsset).

- 'minLength: 1' är satt på 'sensor_id' och 'metric_type' i Kontraktet, eftersom tomma strängar är inte meningsfulla värden och API:et avvisar dem.

