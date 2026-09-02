/**
 * SigV4 signing for HTTP requests to AgentCore /invocations.
 */

import { getAWSCredentials } from './aws-credentials.js';
import { Sha256 } from '@aws-crypto/sha256-js';
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { HttpRequest } from '@smithy/protocol-http';

const region = import.meta.env.VITE_REGION || 'us-east-1';

/**
 * Sign an HTTP POST request to AgentCore with SigV4.
 *
 * @param {string} url - The full AgentCore /invocations URL (may include query params)
 * @param {object} body - The JSON body to send
 * @returns {{ url: string, headers: object }} Signed URL and headers
 */
export async function signInvocation(url, body) {
  const credentials = await getAWSCredentials();
  const parsed = new URL(url);
  const bodyStr = JSON.stringify(body);

  const request = new HttpRequest({
    method: 'POST',
    protocol: parsed.protocol,
    hostname: parsed.hostname,
    path: parsed.pathname,
    query: Object.fromEntries(parsed.searchParams),
    headers: {
      host: parsed.hostname,
      'content-type': 'application/json',
    },
    body: bodyStr,
  });

  const signer = new SignatureV4({
    service: 'bedrock-agentcore',
    region,
    credentials: {
      accessKeyId: credentials.accessKeyId,
      secretAccessKey: credentials.secretAccessKey,
      sessionToken: credentials.sessionToken,
    },
    sha256: Sha256,
  });

  const signed = await signer.sign(request);

  // Reconstruct URL with signed query params
  const qs = Object.entries(signed.query || {})
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  const signedUrl = `${parsed.protocol}//${parsed.hostname}${parsed.pathname}${qs ? '?' + qs : ''}`;

  return { url: signedUrl, headers: signed.headers };
}
