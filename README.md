# Stack AI RAG App

lets setup a v1 architecture implementation for the RAG app , this could evovle once we dive deeper

![system-architecture](./statics/Stack-RAG-system-architecture.png)

### Dividing into mulitple microservices
-  Uploading service
-  Chunking service
-  Embedding service
-  Query Engine


### SAI-DocUploader
A serverless uploader to push fies to object store (s3 for our case)

### SAI-Chunking-Service
Invoked when a S3 object event is created , event driven to scale based on requirement
Mistral API for OCR

### SAI-Embedding-Service
Embedding Servicce - chunks to embedded and stored into the s3

### SAI-Query-Engine
A query engine to handle UI Calls