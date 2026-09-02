import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
} from 'amazon-cognito-identity-js';

const userPoolId = import.meta.env.VITE_USER_POOL_ID;
const clientId = import.meta.env.VITE_USER_POOL_CLIENT_ID;

// Cognito is optional in local dev mode (no VITE_AGENT_RUNTIME_ARN set)
const userPool =
  userPoolId && clientId
    ? new CognitoUserPool({ UserPoolId: userPoolId, ClientId: clientId })
    : null;

export function signIn(email, password) {
  if (!userPool) {
    return Promise.reject(new Error('Authentication not configured'));
  }

  const cognitoUser = new CognitoUser({ Username: email, Pool: userPool });
  const authDetails = new AuthenticationDetails({
    Username: email,
    Password: password,
  });

  return new Promise((resolve, reject) => {
    cognitoUser.authenticateUser(authDetails, {
      onSuccess: (session) => {
        resolve(session.getIdToken().getJwtToken());
      },
      onFailure: (err) => {
        reject(new Error(err.message || 'Sign in failed'));
      },
      // Handle forced password change for admin-created users
      newPasswordRequired: () => {
        cognitoUser.completeNewPasswordChallenge(password, {}, {
          onSuccess: (session) => {
            resolve(session.getIdToken().getJwtToken());
          },
          onFailure: (err) => {
            reject(new Error(err.message || 'Password change failed'));
          },
        });
      },
    });
  });
}

export function signOut() {
  if (!userPool) return;
  const cognitoUser = userPool.getCurrentUser();
  if (cognitoUser) cognitoUser.signOut();

  import('./aws-credentials.js').then(({ clearCredentials }) => {
    clearCredentials();
  });
}

export function getCurrentUser() {
  if (!userPool) return Promise.resolve(null);

  return new Promise((resolve) => {
    const cognitoUser = userPool.getCurrentUser();
    if (!cognitoUser) {
      resolve(null);
      return;
    }

    cognitoUser.getSession((err, session) => {
      if (err || !session.isValid()) {
        resolve(null);
        return;
      }

      cognitoUser.getUserAttributes((attrErr, attributes) => {
        if (attrErr) {
          resolve(null);
          return;
        }

        const email =
          attributes?.find((a) => a.Name === 'email')?.Value || '';
        resolve({ username: cognitoUser.getUsername(), email });
      });
    });
  });
}

export function getIdToken() {
  if (!userPool) return Promise.resolve(null);

  return new Promise((resolve) => {
    const cognitoUser = userPool.getCurrentUser();
    if (!cognitoUser) {
      resolve(null);
      return;
    }

    cognitoUser.getSession((err, session) => {
      if (err || !session.isValid()) {
        resolve(null);
        return;
      }
      resolve(session.getIdToken().getJwtToken());
    });
  });
}
