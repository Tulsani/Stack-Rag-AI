# Stack AI RAG App

lets setup a v1 architecture implementation for the RAG app , this could evovle once we dive deeper

![system-architecture](./statics/Stack-RAG-system-architecture.png)

### Dividing into indivisually scalalbale microservices
-  Uploading service
-  Chunking service
-  Embedding service
-  Query Engine


### SAI-DocUploader
A serverless uploader to push files to object store (S3 for our case).
Endpoint: https://v7rl17dgv1.execute-api.us-east-1.amazonaws.com/default/SAI-docUploader

#### Upload workflow
1. POST metadata to the uploader endpoint.
2. Receive a pre-signed S3 upload URL in the response.
3. PUT the document to S3 using the returned `uploadUrl`.

#### Example metadata request
```bash
curl --location --request POST 'https://v7rl17dgv1.execute-api.us-east-1.amazonaws.com/default/SAI-docUploader' \
  --header 'content-type: application/pdf' \
  --header 'x-doc-filename: acme-nda-v1.pdf' \
  --header 'x-doc-file-size: 204800' \
  --header 'x-doc-client-id: client_acme_001' \
  --header 'x-doc-user-id: user_jane_xyz789' \
  --header 'x-doc-file-type: contract' \
  --header 'x-doc-file-sub-type: nda' \
  --header 'x-doc-doc-type: unstructured' \
  --header 'x-doc-stage: review' \
  --header 'x-doc-parent-folder: deals/2024/q2' \
  --header 'x-doc-uploaded-by: Jane Smith' \
  --header 'x-doc-linked: true' \
  --header 'x-doc-description: Acme Corp NDA for Q2 deal review' \
  --header 'x-doc-tags: [{"key":"region","value":"US"},{"key":"priority","value":"high"}]'
```

#### Example response
```json
{
  "fileId": "1a42c897-28ba-4233-97be-12ef9b3df882",
  "uploadUrl": "https://sai-rag-upload-bucket.s3.us-east-1.amazonaws.com/client_acme_001/deals/2024/q2/1a42c897-28ba-4233-97be-12ef9b3df882.pdf?...",
  "s3Key": "client_acme_001/deals/2024/q2/1a42c897-28ba-4233-97be-12ef9b3df882.pdf",
  "expiresIn": 900,
  "metadata": {
    "fileId": "1a42c897-28ba-4233-97be-12ef9b3df882",
    "clientId": "client_acme_001",
    "userId": "user_jane_xyz789",
    "fileType": "contract",
    "fileSubType": "nda",
    "docType": "unstructured",
    "stage": "review",
    "uploadedBy": "Jane Smith",
    "parentFolder": "deals/2024/q2",
    "description": "Acme Corp NDA for Q2 deal review",
    "tags": [
      { "key": "region", "value": "US" },
      { "key": "priority", "value": "high" }
    ],
    "linked": true,
    "fileName": "acme-nda-v1.pdf",
    "mimeType": "application/pdf",
    "extension": "pdf",
    "fileSize": "204800",
    "s3Key": "client_acme_001/deals/2024/q2/1a42c897-28ba-4233-97be-12ef9b3df882.pdf",
    "s3Bucket": "sai-rag-upload-bucket",
    "uploadStatus": "PENDING"
  }
}
```

#### Upload file to S3
```bash
curl --location --request PUT '<uploadUrl-from-response>' \
  --header 'Content-Type: application/pdf' \
  --form '=@"i_rXjN0Du/Example-file.pdf"'
```


### SAI-Chunking-Service

On file object being created on s3 , event notification is triggered and pushed to a SQS queue (can be replaced with open source alternatives like Kafka/RabbitMQ) 
SQS acts as a buffer to not overwhelm the chunking service and allow it to scale based on incoming requests
The Chunking-Service worker lives in `./SAI-Chunking-Service/app`:

1. Listens to SQS events of S3 object being writed
2. Pickups the S3 object from s3
3. Uses the mistral API to OCR the object 
4. Generates the chunks and stores them to another chunking bucket
5. Informs an SNS to allow the embedder service to pick up the chunks for embedding


- Required env vars:
    - CHUNKING_QUEUE_URL
    - CHUNK_OUTPUT_BUCKET
    - CHUNK_COMPLETE_TOPIC_ARN
    - MISTRAL_API_KEY

- Optional config:
    - MISTRAL_OCR_MODEL
    - CHUNK_TARGET_TOKENS
    - CHUNK_OVERLAP_TOKENS
    - SQS_WAIT_TIME_SECONDS
    - SQS_VISIBILITY_TIMEOUT_SECONDS


### SAI-Embedding-Service
SQS-driven ECS worker that embeds chunk and stores them in PostgreSQL with pgvector. The SNS captures events of completion from chunking service and updates the SQS buffer

1. `chunking-service` writes `chunks.json` to S3.
2. `chunking-service` publishes `DOCUMENT_CHUNKING_COMPLETED` to SNS.
3. SNS delivers the message to the embedding SQS queue.
4. This worker long-polls SQS, downloads the chunk artifact from S3, embeds each chunk with Mistral, and writes rows into `sairag.public.chunks`.
5. The query engine can combine vector search over `embedding` with keyword search over `content_tsv`.

#### table setup

The worker inserts into the table :

```sql
CREATE TABLE chunks (
    chunk_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id       TEXT NOT NULL,
    filename      TEXT NOT NULL,
    client_id     TEXT,
    user_id       TEXT,
    file_type     TEXT,
    file_sub_type TEXT,
    doc_type      TEXT,
    stage         TEXT,
    page_start    INT,
    page_end      INT,
    chunk_index   INT NOT NULL,
    content       TEXT NOT NULL,
    embedding     vector(1024),
    metadata      JSONB DEFAULT '{}'::jsonb,
    content_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at    TIMESTAMPTZ DEFAULT now()
);
```

The worker treats a file embedding job as replaceable/idempotent: inside one transaction it deletes existing rows for `file_id`, then inserts the current artifact chunks. This avoids duplicate rows when SQS retries the same completion message.



### SAI-Query-Engine
FastAPI service for querying chunks embedded into PostgreSQL/pgvector.

#### Endpoints

- `GET /health`
- `POST /query`: semantic pgvector retrieval.
- `POST /query/hybrid`: semantic pgvector retrieval plus PostgreSQL full-text keyword retrieval over `content_tsv`.

#### Semantic Query

```bash
curl --location 'http://localhost:8000/query' \
  --header 'Content-Type: application/json' \
  --data '{
    "question": "Is Akshat Tulsani a good fit for stackAI? Stack AI is building ai agents in healthcare and designing rag solutions ",
    "top_k": 5
  }'
```

#### Hybrid Query

```bash
curl --location 'http://localhost:8000/query/hybrid' \
  --header 'Content-Type: application/json' \
  --data '{
    "question": "What does the uploaded document say about termination?",
    "top_k": 5,
    "semantic_weight": 0.65,
    "keyword_weight": 0.35
  }'
```

The keyword side uses `websearch_to_tsquery('english', question)` and `ts_rank_cd(content_tsv, query)`. The final result order is merged with reciprocal rank fusion.

Both query endpoints use multi-query rewriting by default. The original question is always included, and Mistral can generate up to 3 extra retrieval queries. The response includes `rewritten_queries` for debugging

Disable rewriting for debugging:

```json
{
  "question": "What does the uploaded document say about termination?",
  "use_query_rewrite": false
}
```

Post-processing is lightweight: results from the original question and rewritten queries are merged, duplicate chunks are removed by `chunk_id`, and candidates are reranked by the best available retrieval score before selecting the final `top_k`.

#### Run Locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

export MISTRAL_API_KEY=replace-me
export POSTGRES_HOST=<db.name>
export POSTGRES_DB=**
export POSTGRES_USER=***
export POSTGRES_PASSWORD=replace-me
export POSTGRES_SSLMODE=require

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```