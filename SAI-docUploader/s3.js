import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { MIME_TO_EXTENSION, DEFAULT_PRESIGN_EXPIRY_SECONDS } from './types.js';

const s3Client = new S3Client({});

const BUCKET      = process.env.UPLOAD_BUCKET;
const EXPIRY_SECS = parseInt(process.env.PRESIGN_EXPIRY_SECONDS ?? String(DEFAULT_PRESIGN_EXPIRY_SECONDS), 10);

if (!BUCKET) throw new Error('UPLOAD_BUCKET environment variable is required');

//  S3 key strategy 

export const buildS3Key = (fileId, metadata, ext) => {
  const parts = [metadata.clientId];
  if (metadata.parentFolder) {
    // strip leading/trailing slashes so we never get double-slashes
    parts.push(metadata.parentFolder.replace(/^\/+|\/+$/g, ''));
  }
  parts.push(`${fileId}.${ext}`);
  return parts.join('/');
};

//  S3 object metadata 

const buildS3ObjectMetadata = (fileId, metadata) => ({
  'file-id':       fileId,
  'client-id':     metadata.clientId,
  'user-id':       metadata.userId,
  'file-type':     metadata.fileType,
  'file-sub-type': metadata.fileSubType  ?? '',
  'doc-type':      metadata.docType      ?? '',
  'stage':         metadata.stage        ?? '',
  'parent-folder': metadata.parentFolder ?? '',
  'uploaded-by':   metadata.uploadedBy   ?? '',
  'linked':        String(metadata.linked ?? false),
  'tags':          JSON.stringify(metadata.tags ?? []),
  'description':   metadata.description  ?? '',
});

//  Presigned URL generator 

export const generatePresignedPutUrl = async (fileId, contentType, fileSizeBytes, metadata) => {
  const ext   = MIME_TO_EXTENSION[contentType];
  const s3Key = buildS3Key(fileId, metadata, ext);

  const command = new PutObjectCommand({
    Bucket:      BUCKET,
    Key:         s3Key,
    ContentType: contentType,
    Metadata:    buildS3ObjectMetadata(fileId, metadata),
  });

  const uploadUrl = await getSignedUrl(s3Client, command, { expiresIn: EXPIRY_SECS });

  return { uploadUrl, s3Key, expiresIn: EXPIRY_SECS };
};