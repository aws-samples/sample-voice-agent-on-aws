import VoiceChat from './components/VoiceChat';
import { AuthProvider, useAuth } from './contexts/AuthContext.jsx';
import AuthScreen from './components/AuthScreen.jsx';

const needsAuth = !!import.meta.env.VITE_AGENT_RUNTIME_ARN;

function AppContent() {
  const { user, loading, signOut } = useAuth();

  if (needsAuth && loading) {
    return <div style={styles.loading}>Loading...</div>;
  }

  if (needsAuth && !user) {
    return <AuthScreen />;
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>Family Recipe Assistant</h1>
        {user && (
          <button onClick={signOut} style={styles.signOutButton}>
            Sign Out
          </button>
        )}
      </header>
      <main style={styles.main}>
        <p style={styles.subtitle}>Voice-powered recipe search, timers, nutrition, and conversions</p>
        <VoiceChat />
      </main>
    </div>
  );
}

export default function App() {
  if (!needsAuth) {
    return (
      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.title}>Family Recipe Assistant</h1>
        </header>
        <main style={styles.main}>
          <p style={styles.subtitle}>Voice-powered recipe search, timers, nutrition, and conversions</p>
          <VoiceChat />
        </main>
      </div>
    );
  }

  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },
  header: {
    background: '#2d5016',
    padding: '0.75rem 1rem',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontSize: '1.25rem',
    fontWeight: 600,
    color: '#ffffff',
  },
  signOutButton: {
    background: 'transparent',
    border: '1px solid rgba(255, 255, 255, 0.5)',
    color: '#ffffff',
    padding: '0.3rem 0.75rem',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '0.8rem',
  },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    maxWidth: 520,
    margin: '0 auto',
    padding: '2rem 1rem',
    width: '100%',
  },
  subtitle: {
    fontSize: '0.85rem',
    color: '#666666',
    marginBottom: '2rem',
  },
  loading: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    color: '#666666',
  },
};
