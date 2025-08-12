# Simple Orchestrator with Job Counters

Цей документ описує простий і дешевий "оркестратор" на основі лічильників у Jobs таблиці для координації обробки треків і автоматичного створення плейлістів.

## Архітектура

```
BeatportScraper → S3 → ChartProcessor → SNS → SQS → YoutubeMusicSearch
       ↓              ↓                              ↓
   EventBridge    JobsTable                    JobsTable
       ↓              ↓                              ↓
   Schedule       Create Job                  Update Counters
                     ↓                              ↓
                 expected_count              processed_count++
                                                    ↓
                                           processed == expected?
                                                    ↓
                                            EventBridge Event
                                                    ↓
                                          YoutubePlaylistFunction
```

## Потік обробки

### 1. Scraping (вже існує)
- **BeatportScraperFunction** пише `.json` у `PlaylistsBucket` за розкладом
- Використовує **EventBridge** тригер кожного тижня
- S3 подія автоматично тригерить **ChartProcessorFunction**

### 2. Chart Processing (оновлено)
**ChartProcessorFunction** отримує S3-подію і:
1. Вибирає нові треки (які не існують у TracksTable)
2. **Створює job record** у JobsTable:
   ```json
   {
     "job_id": "uuid",
     "source_file": "beatport/2024/08/12/top100.json",
     "expected_count": 25,
     "processed_count": 0,
     "status": "processing",
     "created_at": "2024-08-12T10:00:00Z"
   }
   ```
3. Розсилає повідомлення до SNS з `job_id`
4. SNS → SQS (YouTubeMusicProcessingQueue)

### 3. YouTube Processing (оновлено)
**YoutubeMusicSearchFunction** читає з SQS батчами і:
1. Обробляє кожен трек (пошук YouTube ID)
2. Оновлює TracksTable
3. **Атомарно інкрементує** `processed_count` у JobsTable
4. **Перевіряє**: `processed_count == expected_count`?
5. Якщо ТАК → відмічає job як `completed` і кидає **JobCompleted** подію

### 4. Playlist Creation (оновлено)
**YoutubePlaylistFunction** тепер має два тригери:
1. **HTTP API** (як раніше) - для ручних викликів
2. **EventBridge Rule** - для автоматичних викликів після JobCompleted

Коли отримує JobCompleted подію:
1. Автоматично створює назву плейліста
2. Читає треки з S3
3. Збагачує YouTube ID з TracksTable
4. Створює публічний YouTube плейліст

## Переваги оркестратора

### 1. Простота
- Немає складних state machines
- Використовує звичайні AWS сервіси
- Легко зрозуміти і debug-ити

### 2. Дешевизна
- Лічильники у DynamoDB (копійки)
- EventBridge події (копійки)
- Немає Step Functions ($$$)

### 3. Надійність
- Атомарні операції з лічильниками
- Dead Letter Queues для невдалих повідомлень
- Повторні спроби на рівні SQS

### 4. Масштабованість
- SQS батчі (BatchSize=10, Window=5с)
- Паралельна обробка треків
- DynamoDB auto-scaling

## Конфігурація

### Jobs Table Schema
```yaml
JobsTable:
  AttributeDefinitions:
    - AttributeName: job_id
      AttributeType: S
  KeySchema:
    - AttributeName: job_id
      KeyType: HASH
```

### Environment Variables
Всі функції мають доступ до:
- `JOBS_TABLE` - назва Jobs таблиці
- `EVENT_BUS_NAME` - EventBridge bus (default)
- `PLAYLISTS_BUCKET` - S3 bucket з чартами

### IAM Rights
**ChartProcessorFunction**:
- `DynamoDBCrudPolicy` на Jobs + Tracks таблиці
- `SNSPublishMessagePolicy`

**YoutubeMusicSearchFunction**:
- `DynamoDBCrudPolicy` на Jobs + Tracks таблиці
- `events:PutEvents` на EventBridge

**YoutubePlaylistFunction**:
- `DynamoDBCrudPolicy` на всі таблиці
- EventBridge Rule тригер

## Моніторинг

### CloudWatch Metrics
- Job completion time
- Success/failure rates per job
- Queue depths
- Dead letter queue messages

### CloudWatch Logs
Кожна функція логує:
- Job ID та progress
- Помилки з деталями
- Timing інформацію

### EventBridge Events
```json
{
  "source": "music-search.orchestrator",
  "detail-type": "Job Completed",
  "detail": {
    "job_id": "uuid",
    "source_file": "beatport/...",
    "expected_count": 25,
    "processed_count": 25,
    "s3_bucket": "bucket",
    "s3_key": "path/to/chart.json"
  }
}
```

## Troubleshooting

### Job застряг у processing
1. Перевір Dead Letter Queues
2. Перевір CloudWatch Logs функцій
3. Ручно зменш `expected_count` або збільш `processed_count`

### Плейліст не створився
1. Перевір EventBridge Rules (enabled?)
2. Перевір Dead Letter Queue YoutubePlaylistFunction
3. Перевір YouTube OAuth credentials у SSM

### Дублікати треків
- Jobs Table запобігає дублікатам на рівні job
- TracksTable має hash-based IDs для унікальності

## Testing

Локальне тестування:
```bash
python test_orchestrator.py
```

AWS тестування:
```bash
# Ручний тригер scraper
curl "https://api.../scrape"

# Перевір Jobs Table
aws dynamodb scan --table-name charts-vibe-jobs

# Перевір EventBridge events
aws logs filter-log-events --log-group-name /aws/lambda/youtube-playlist-function
```

## Deployment

Deployment через SAM:
```bash
sam build && sam deploy
```

Основні зміни в template.yaml:
- Додано права на JobsTable для всіх функцій
- EventBridge Rule для YoutubePlaylistFunction
- Dead Letter Queue для playlist processing
- Environment variables для EventBridge
