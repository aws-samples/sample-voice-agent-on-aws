import { createContext, useContext, useState, useEffect } from 'react';
import { getCurrentUser, signIn as cognitoSignIn, signOut as cognitoSignOut } from '../auth.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const signIn = async (email, password) => {
    await cognitoSignIn(email, password);
    const currentUser = await getCurrentUser();
    setUser(currentUser);
  };

  const signOut = () => {
    cognitoSignOut();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
