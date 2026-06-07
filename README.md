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
Embedding Servicce - chunks to embedded and stored into the s3

### SAI-Query-Engine
A query engine to handle UI Calls