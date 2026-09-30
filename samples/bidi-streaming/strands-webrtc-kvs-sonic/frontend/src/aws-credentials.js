/**
 * Exchange Cognito JWT for temporary AWS credentials via Identity Pool.
 * These credentials are used to sign WebSocket requests to AgentCore with SigV4.
 */

import {
  CognitoIdentityClient,
  GetIdCommand,
  GetCredentialsForIdentityCommand,
} from '@aws-sdk/client-cognito-identity';
import { getIdToken } from './auth.js';

const region = import.meta.env.VITE_REGION || 'us-east-1';
const userPoolId = import.meta.env.VITE_USER_POOL_ID;
const identityPoolId = import.meta.env.VITE_IDENTITY_POOL_ID;

let cachedCredentials = null;
let credentialsExpiry = null;

export async function getAWSCredentials() {
  // Return cached credentials if still valid (with 5 min buffer)
  if (cachedCredentials && credentialsExpiry) {
    const bufferMs = 5 * 60 * 1000;
    if (credentialsExpiry.getTime() - Date.now() > bufferMs) {
      return cachedCredentials;
    }
  }

  const idToken = await getIdToken();
  if (!idToken) throw new Error('Not authenticated - please sign in');
  if (!identityPoolId) throw new Error('Identity Pool ID not configured');

  const client = new CognitoIdentityClient({ region });
  const providerName = `cognito-idp.${region}.amazonaws.com/${userPoolId}`;

  // Step 1: Get identity ID
  const { IdentityId } = await client.send(
    new GetIdCommand({
      IdentityPoolId: identityPoolId,
      Logins: { [providerName]: idToken },
    })
  );

  if (!IdentityId) throw new Error('Failed to get identity ID');

  // Step 2: Get temporary AWS credentials
  const { Credentials } = await client.send(
    new GetCredentialsForIdentityCommand({
      IdentityId,
      Logins: { [providerName]: idToken },
    })
  );

  if (!Credentials?.AccessKeyId || !Credentials?.SecretKey || !Credentials?.SessionToken) {
    throw new Error('Failed to get AWS credentials');
  }

  cachedCredentials = {
    accessKeyId: Credentials.AccessKeyId,
    secretAccessKey: Credentials.SecretKey,
    sessionToken: Credentials.SessionToken,
    expiration: Credentials.Expiration,
  };
  credentialsExpiry = Credentials.Expiration || null;

  return cachedCredentials;
}

export function clearCredentials() {
  cachedCredentials = null;
  credentialsExpiry = null;
}
