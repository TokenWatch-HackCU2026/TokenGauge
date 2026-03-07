# TokenWatch — Skills & Patterns

Reusable implementation patterns and code conventions for the TokenWatch codebase.

---

## AWS KMS Envelope Encryption

**When to use**: Encrypting user AI provider keys before storage.

```typescript
import { KMSClient, GenerateDataKeyCommand, DecryptCommand } from '@aws-sdk/client-kms';
import { createCipheriv, createDecipheriv, randomBytes } from 'crypto';

const kms = new KMSClient({ region: process.env.AWS_REGION });

// Encrypt a raw key for storage
export async function encryptKey(rawKey: string): Promise<{ encryptedBlob: string; keyHint: string }> {
  // 1. Ask KMS for a data key
  const { Plaintext: dataKey, CiphertextBlob: encryptedDataKey } = await kms.send(
    new GenerateDataKeyCommand({ KeyId: process.env.KMS_KEY_ID!, KeySpec: 'AES_256' })
  );

  // 2. Encrypt the raw key with the data key (AES-256-GCM)
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', dataKey!, iv);
  const encrypted = Buffer.concat([cipher.update(rawKey, 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();

  // 3. Pack: [encryptedDataKey | iv | authTag | encrypted]
  const blob = Buffer.concat([
    Buffer.from(encryptedDataKey!),
    iv,
    authTag,
    encrypted
  ]).toString('base64');

  // Clear data key from memory
  dataKey!.fill(0);

  return {
    encryptedBlob: blob,
    keyHint: rawKey.slice(-4),
  };
}

// Decrypt a blob back to the raw key (in-memory only — never persist the result)
export async function decryptKey(encryptedBlob: string): Promise<string> {
  const buf = Buffer.from(encryptedBlob, 'base64');
  // Note: encryptedDataKey is first 184 bytes for a 256-bit KMS key ciphertext
  const encryptedDataKey = buf.slice(0, 184);
  const iv = buf.slice(184, 196);
  const authTag = buf.slice(196, 212);
  const encrypted = buf.slice(212);

  const { Plaintext: dataKey } = await kms.send(
    new DecryptCommand({ CiphertextBlob: encryptedDataKey, KeyId: process.env.KMS_KEY_ID! })
  );

  const decipher = createDecipheriv('aes-256-gcm', dataKey!, iv);
  decipher.setAuthTag(authTag);
  const rawKey = decipher.update(encrypted).toString('utf8') + decipher.final('utf8');

  dataKey!.fill(0); // Clear data key from memory
  return rawKey;
}
```

---

## Redis Sliding Window Rate Limiter

**When to use**: Per-user quota enforcement in the proxy middleware.

```typescript
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL!);

// Lua script for atomic sliding window check
const rateLimitScript = `
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local windowStart = now - window

redis.call('ZREMRANGEBYSCORE', key, '-inf', windowStart)
local count = redis.call('ZCARD', key)

if count >= limit then
  return {0, count, windowStart + window}
end

redis.call('ZADD', key, now, now .. math.random(1000000))
redis.call('EXPIRE', key, math.ceil(window / 1000))
return {1, count + 1, windowStart + window}
`;

export async function checkRateLimit(
  userId: string,
  limit: number,
  windowMs: number
): Promise<{ allowed: boolean; remaining: number; resetAt: number }> {
  const now = Date.now();
  const key = `ratelimit:${userId}`;
  const result = await redis.eval(rateLimitScript, 1, key, now, windowMs, limit) as number[];
  return {
    allowed: result[0] === 1,
    remaining: Math.max(0, limit - result[1]),
    resetAt: result[2],
  };
}
```

---

## JWT Middleware

**When to use**: Protecting any Express route that requires authentication.

```typescript
import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

export interface AuthRequest extends Request {
  user?: { userId: string; orgId: string; email: string };
}

export function requireAuth(req: AuthRequest, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing authorization header' });
  }

  try {
    const token = header.slice(7);
    const payload = jwt.verify(token, process.env.JWT_SECRET!) as any;
    req.user = { userId: payload.sub, orgId: payload.orgId, email: payload.email };
    next();
  } catch {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
}
```

---

## Zod Request Validation Middleware

**When to use**: Validating request bodies on any route.

```typescript
import { Request, Response, NextFunction } from 'express';
import { ZodSchema } from 'zod';

export function validate(schema: ZodSchema) {
  return (req: Request, res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      return res.status(400).json({ error: 'Validation failed', details: result.error.flatten() });
    }
    req.body = result.data;
    next();
  };
}
```

---

## MongoDB Usage Query (Aggregation Pipeline)

**When to use**: Dashboard usage data endpoints.

```typescript
import { ApiCall } from '../models/ApiCall';

export async function getUsageSummary(
  userId: string,
  startDate: Date,
  endDate: Date,
  groupBy: 'hour' | 'day' = 'day'
) {
  const dateFormat = groupBy === 'hour' ? '%Y-%m-%dT%H:00:00Z' : '%Y-%m-%d';

  return ApiCall.aggregate([
    {
      $match: {
        userId,
        timestamp: { $gte: startDate, $lte: endDate },
      },
    },
    {
      $group: {
        _id: {
          date: { $dateToString: { format: dateFormat, date: '$timestamp' } },
          provider: '$provider',
          model: '$model',
        },
        totalTokensIn: { $sum: '$tokensIn' },
        totalTokensOut: { $sum: '$tokensOut' },
        totalCostUsd: { $sum: '$costUsd' },
        requestCount: { $sum: 1 },
        avgLatencyMs: { $avg: '$latencyMs' },
      },
    },
    { $sort: { '_id.date': 1 } },
  ]);
}
```

---

## BullMQ Job Queue

**When to use**: Async alert delivery, webhook dispatch, usage summarization.

```typescript
import { Queue, Worker } from 'bullmq';
import Redis from 'ioredis';

const connection = new Redis(process.env.REDIS_URL!, { maxRetriesPerRequest: null });

// Define queues
export const alertQueue = new Queue('alerts', { connection });
export const webhookQueue = new Queue('webhooks', { connection });

// Enqueue a webhook delivery job
export async function enqueueWebhook(payload: WebhookPayload) {
  await webhookQueue.add('deliver', payload, {
    attempts: 3,
    backoff: { type: 'exponential', delay: 2000 },
  });
}

// Worker (run in separate process or worker thread)
const webhookWorker = new Worker(
  'webhooks',
  async (job) => {
    const { url, payload } = job.data;
    await axios.post(url, payload, { timeout: 5000 });
  },
  { connection }
);
```

---

## Provider Adapter Interface

**When to use**: Adding new AI provider support to the gateway.

```typescript
export interface ProviderRequest {
  model: string;
  messages: Array<{ role: string; content: string }>;
  maxTokens?: number;
  temperature?: number;
}

export interface ProviderResponse {
  content: string;
  tokensIn: number;
  tokensOut: number;
  model: string;
  rawResponse: unknown;
}

export interface IProviderAdapter {
  provider: string;
  forward(request: ProviderRequest, apiKey: string): Promise<ProviderResponse>;
}
```

---

## Cost Calculation

**When to use**: After every proxy response to calculate USD cost.

```typescript
const PRICING: Record<string, { input: number; output: number }> = {
  'claude-3-haiku':        { input: 0.25,  output: 1.25  },
  'claude-3-5-sonnet':     { input: 3.00,  output: 15.00 },
  'gpt-4o-mini':           { input: 0.15,  output: 0.60  },
  'gpt-4o':                { input: 5.00,  output: 15.00 },
  'gemini-1.5-flash':      { input: 0.075, output: 0.30  },
  'gemini-1.5-pro':        { input: 3.50,  output: 10.50 },
  'mistral-small':         { input: 1.00,  output: 3.00  },
  'mistral-large':         { input: 8.00,  output: 24.00 },
};

export function calculateCost(model: string, tokensIn: number, tokensOut: number): number {
  const price = PRICING[model];
  if (!price) return 0;
  return (tokensIn / 1_000_000) * price.input + (tokensOut / 1_000_000) * price.output;
}
```
