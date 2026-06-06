import { DynamoDBClient, PutItemCommand } from '@aws-sdk/client-dynamodb';
import { marshall } from '@aws-sdk/util-dynamodb';

const ddbClient = new DynamoDBClient({});

const TABLE = process.env.DOCUMENTS_TABLE;
if (!TABLE) throw new Error('DOCUMENTS_TABLE environment variable is required');


export const persistFileRecord = async (record) => {
  await ddbClient.send(
    new PutItemCommand({
      TableName: TABLE,
      Item: marshall(record, { removeUndefinedValues: true }),
      ConditionExpression: 'attribute_not_exists(fileId)',
    })
  );
};