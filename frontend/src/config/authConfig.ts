import { LogLevel, Configuration, PublicClientApplication } from '@azure/msal-browser';

export const msalConfig: Configuration = {
  auth: {
    clientId: process.env.REACT_APP_AZURE_CLIENT_ID || '',
    authority: `https://login.microsoftonline.com/${process.env.REACT_APP_AZURE_TENANT_ID || ''}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        switch (level) {
          case LogLevel.Error:
            console.error('MSAL Error:', message);
            return;
          case LogLevel.Warning:
            console.warn('MSAL Warning:', message);
            return;
          case LogLevel.Info:
            console.info('MSAL Info:', message);
            return;
        }
      },
    },
    allowNativeBroker: false,
  },
};

export const loginRequest = {
  scopes: ['openid', 'profile', 'email'],
};

export const graphConfig = {
  graphMeEndpoint: 'https://graph.microsoft.com/v1.0/me',
};

export const appSpecificLoginRequest = {
  scopes: [`api://${process.env.REACT_APP_AZURE_CLIENT_ID}/.default`],
};

// Create a single MSAL instance to be shared across the app
export const msalInstance = new PublicClientApplication(msalConfig);

// 環境変数が設定されているか確認
console.log('MSAL Config Check:');
console.log('Client ID:', process.env.REACT_APP_AZURE_CLIENT_ID ? 'Set' : 'Missing');
console.log('Tenant ID:', process.env.REACT_APP_AZURE_TENANT_ID ? 'Set' : 'Missing');
console.log('Authority:', msalConfig.auth.authority);
console.log('Redirect URI:', msalConfig.auth.redirectUri);
